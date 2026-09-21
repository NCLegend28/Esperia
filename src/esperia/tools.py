"""Typed, explicitly granted research tools with durable per-job accounting.

Example: registry.register('web_search', description, Request, Result, search)
Then ToolRuntime(registry, grants, output, max_calls=3).invoke(name, arguments).
This synchronous foundation deliberately stops on failures; it is not a worker queue.
"""

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

A = TypeVar("A", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)


class ToolError(ValueError):
    """Application-authored diagnostic safe to show without raw provider errors."""


@dataclass(frozen=True)
class ToolDefinition:
    """Tool contract and executor; only owner/application code registers tools."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    validate: Callable[[dict[str, Any]], None]
    execute: Callable[[dict[str, Any]], dict[str, Any]]


class ToolRegistry:
    """Register typed operations once, without discovering executable model text."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        arguments: type[A],
        result: type[R],
        handler: Callable[[A], R],
    ) -> None:
        """Bind input/output validation to an explicit application-owned handler."""
        if not name or name in self._tools:
            raise ValueError("Tool names must be nonempty and unique")

        def validate(value: dict[str, Any]) -> None:
            arguments.model_validate(value, strict=True)

        def execute(value: dict[str, Any]) -> dict[str, Any]:
            request = arguments.model_validate(value, strict=True)
            response = result.model_validate(
                handler(request).model_dump(warnings="error"), strict=True
            )
            return response.model_dump(mode="json")

        self._tools[name] = ToolDefinition(
            name,
            description,
            arguments.model_json_schema(),
            result.model_json_schema(),
            validate,
            execute,
        )

    def get(self, name: str) -> ToolDefinition:
        """Resolve only registered operations, never imports or shell commands."""
        if name not in self._tools:
            raise ToolError("Requested tool is not registered")
        return self._tools[name]


class ToolRuntime:
    """Enforce immutable grants and atomically reserve calls in a job-local journal.

    Separate runtime objects sharing a journal share its budget. Interrupted or
    failed calls block further dispatch, requiring an explicit new research job;
    no automatic replay or reconciliation is claimed. Handlers own bounded I/O.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        grants: frozenset[str],
        output: Path,
        *,
        max_calls: int,
        output_bytes: int = 24000,
        sqlite_timeout: int = 10,
        per_tool_limits: dict[str, int] | None = None,
        per_tool_output_bytes: dict[str, int] | None = None,
    ):
        if max_calls < 1 or output_bytes < 1:
            raise ValueError("Tool budgets must be positive")
        self.registry, self.grants = registry, grants
        self.max_calls, self.output_bytes = max_calls, output_bytes
        self.sqlite_timeout = sqlite_timeout
        self.per_tool_limits = dict(per_tool_limits or {})
        self.per_tool_output_bytes = dict(per_tool_output_bytes or {})
        if any(
            name not in grants or limit < 1
            for name, limit in [
                *self.per_tool_limits.items(),
                *self.per_tool_output_bytes.items(),
            ]
        ):
            raise ValueError(
                "Per-tool limits require granted tools and positive bounds"
            )
        output.mkdir(parents=True, exist_ok=True)
        self.path = output / "tool-calls.sqlite"
        for name in grants:
            registry.get(name)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS calls (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, arguments TEXT NOT NULL,
                state TEXT NOT NULL, started_at TEXT NOT NULL, result TEXT,
                code TEXT
            )""")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=self.sqlite_timeout)
        try:
            with db:
                yield db
        finally:
            db.close()

    def describe(self) -> list[dict[str, Any]]:
        """Expose only granted schemas; tools cannot grant additional tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
            }
            for name in sorted(self.grants)
            for tool in [self.registry.get(name)]
        ]

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate, reserve, execute once, and persist bounded results or failure."""
        if name not in self.grants:
            raise ToolError("Requested tool is not granted for this task")
        tool = self.registry.get(name)
        try:
            tool.validate(arguments)
            serialized = json.dumps(arguments, allow_nan=False)
        except (ValidationError, ValueError, TypeError):
            raise ToolError("Tool arguments do not match the granted schema") from None
        call_id = str(uuid4())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM calls WHERE state != 'completed'").fetchone():
                raise ToolError(
                    "An interrupted or failed tool call requires inspection; no automatic replay"
                )
            if db.execute("SELECT COUNT(*) FROM calls").fetchone()[0] >= self.max_calls:
                raise ToolError("Research tool-call budget exhausted")
            if (
                name in self.per_tool_limits
                and db.execute(
                    "SELECT COUNT(*) FROM calls WHERE name=?", (name,)
                ).fetchone()[0]
                >= self.per_tool_limits[name]
            ):
                raise ToolError("This tool's call budget is exhausted")
            db.execute(
                "INSERT INTO calls (id,name,arguments,state,started_at) VALUES (?,?,?,?,?)",
                (call_id, name, serialized, "running", datetime.now(UTC).isoformat()),
            )
        try:
            result = tool.execute(arguments)
            encoded = json.dumps(result, allow_nan=False)
            if len(encoded.encode()) > self.per_tool_output_bytes.get(
                name, self.output_bytes
            ):
                raise ToolError("Tool result exceeds the configured output budget")
        except Exception:
            with self._connect() as db:
                db.execute(
                    "UPDATE calls SET state='failed', code=? WHERE id=?",
                    ("tool_execution_failed", call_id),
                )
            raise ToolError(
                "Research tool failed; inspect tool-calls.sqlite and configuration. No automatic retry"
            ) from None
        with self._connect() as db:
            db.execute(
                "UPDATE calls SET state='completed', result=? WHERE id=?",
                (encoded, call_id),
            )
        return result
