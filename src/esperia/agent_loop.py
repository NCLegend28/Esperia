"""Durable bounded decide/act/observe execution, independent of models and tools.

Example: run_loop(journal, choose, execute, validate_finish, limits).
Callbacks receive saved observations; only registered application code executes actions.
"""

import fcntl
import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from esperia.settings import LoopSettings


class LoopError(ValueError):
    """Safe framework diagnostic without provider or source content."""


class LoopHalted(LoopError):
    """Execution paused, stopped or blocked at an explicit boundary."""


class Action(BaseModel):
    """Internal action normalized from a domain-specific validated model schema."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["tool", "finish", "blocked"]
    name: str
    arguments: dict[str, Any]


class Journal:
    """Persist decisions, observations and owner controls in a per-run database.

    A process lock prevents concurrent workers. A pending checkpoint is never
    replayed after a crash: its external outcome may be unknown.
    """

    def __init__(self, output: Path, timeout: int = 10):
        self.output = output
        self.path = output / "agent.sqlite"
        self.timeout = timeout

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=self.timeout)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, request: dict[str, Any]) -> None:
        """Initialize a new run, refusing to overwrite an existing request."""
        self.output.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS run (id INTEGER PRIMARY KEY CHECK(id=1), request TEXT NOT NULL, status TEXT NOT NULL, control TEXT NOT NULL, pending TEXT, reason TEXT NOT NULL, elapsed REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS steps (number INTEGER PRIMARY KEY, action TEXT NOT NULL, observation TEXT NOT NULL)"
            )
            if db.execute("SELECT 1 FROM run").fetchone():
                raise LoopError("Agent run already exists")
            db.execute(
                "INSERT INTO run VALUES (1,?,'ready','run',NULL,'',0)",
                (json.dumps(request),),
            )

    def snapshot(self) -> dict[str, Any]:
        """Read persisted public execution state without calling a model."""
        if not self.path.is_file():
            raise LoopError("This job has no adaptive execution journal")
        with self.connect() as db:
            row = db.execute("SELECT * FROM run WHERE id=1").fetchone()
            if row is None:
                raise LoopError("Agent journal is incomplete")
            value = dict(row)
            value["request"] = json.loads(value["request"])
            value["steps"] = [
                {
                    "number": row["number"],
                    "action": json.loads(row["action"]),
                    "observation": json.loads(row["observation"]),
                }
                for row in db.execute("SELECT * FROM steps ORDER BY number")
            ]
            return value

    @contextmanager
    def worker(self) -> Iterator[None]:
        """One process owns a run; owner controls remain available concurrently."""
        with (self.output / "agent.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise LoopError("Another worker already owns this agent run") from None
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def control(self, action: Literal["pause", "stop", "resume"]) -> None:
        """Owner-only control. Resume never clears pending or uncertain work."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM run WHERE id=1").fetchone()
            if row is None or row["status"] in {"completed", "stopped", "blocked"}:
                raise LoopError(
                    "Run is terminal; inspect its outcome before creating new work"
                )
            if action == "resume":
                if row["pending"] is not None or row["control"] == "stop":
                    raise LoopError("Pending execution cannot be resumed or replayed")
                db.execute("UPDATE run SET control='run',status='ready' WHERE id=1")
            else:
                db.execute(
                    "UPDATE run SET control=?,status=CASE WHEN pending IS NULL THEN ? ELSE status END,reason=? WHERE id=1",
                    (
                        action,
                        "paused" if action == "pause" else "stopped",
                        f"owner_{action}",
                    ),
                )

    def boundary(self) -> None:
        """Honor owner controls before the next external action."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            control = db.execute("SELECT control FROM run WHERE id=1").fetchone()[0]
            if control != "run":
                state = "paused" if control == "pause" else "stopped"
                db.execute(
                    "UPDATE run SET status=?,reason=? WHERE id=1",
                    (state, f"owner_{control}"),
                )
            else:
                return
        raise LoopHalted(f"Agent {state} at an execution boundary")

    def begin(self, phase: str) -> None:
        """Atomically honor controls and mark an external action in flight."""
        self.boundary()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT control,pending FROM run WHERE id=1").fetchone()
            if row["control"] != "run":
                raise LoopHalted("Owner control requested before dispatch")
            if row["pending"] is not None:
                raise LoopError("Execution outcome is uncertain; no automatic replay")
            db.execute("UPDATE run SET status='running',pending=? WHERE id=1", (phase,))

    def record(self, action: Action, observation: dict[str, Any]) -> None:
        """Commit a complete observation and clear the external-action marker."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            number = db.execute("SELECT COUNT(*)+1 FROM steps").fetchone()[0]
            db.execute(
                "INSERT INTO steps VALUES (?,?,?)",
                (
                    number,
                    action.model_dump_json(),
                    json.dumps(observation, allow_nan=False),
                ),
            )
            db.execute("UPDATE run SET pending=NULL WHERE id=1")

    def mark(self, status: str, reason: str, *, clear: bool = False) -> None:
        """Record an application-authored terminal state or a known checkpoint."""
        with self.connect() as db:
            db.execute(
                "UPDATE run SET status=?,reason=?,pending=CASE WHEN ? THEN NULL ELSE pending END WHERE id=1",
                (status, reason, clear),
            )

    def add_elapsed(self, seconds: float) -> None:
        """Accumulate active wall time across explicit resumptions."""
        with self.connect() as db:
            db.execute("UPDATE run SET elapsed=elapsed+? WHERE id=1", (seconds,))


def run_loop(
    journal: Journal,
    choose: Callable[[list[dict[str, Any]], int], Action],
    execute: Callable[[Action], dict[str, Any]],
    finish: Callable[[Action], dict[str, Any]],
    limits: LoopSettings,
) -> dict[str, Any]:
    """Run under journal.worker(); persist choices before tools and stop on stalls.

    A saved decision is safe to consume after a pause. A decision/tool still in
    flight after process loss is not safe to replay. Completion invokes a trusted
    validator; the model's finish request alone never constitutes acceptance.
    """
    started = time.monotonic()
    initial = journal.snapshot()
    if initial["pending"] is not None:
        journal.mark("blocked", "uncertain_execution")
        raise LoopHalted(
            "Previous execution may have run; inspect saved calls. No replay"
        )
    if initial["status"] in {"completed", "blocked", "stopped"}:
        raise LoopHalted("Agent run is terminal")
    try:
        while True:
            journal.boundary()
            state = journal.snapshot()
            history = state["steps"]
            if state["elapsed"] + time.monotonic() - started >= limits.seconds:
                journal.mark("blocked", "time_budget")
                raise LoopHalted("Agent active-time budget exhausted")
            # Decisions are checkpoints too, allowing pause after inference without paying again.
            decision_rows = [s for s in history if s["observation"].get("decision")]
            pending_decision = history and history[-1]["observation"].get("decision")
            if pending_decision:
                action = Action.model_validate(history[-1]["action"])
            else:
                if len(decision_rows) >= limits.steps:
                    journal.mark("blocked", "step_budget")
                    raise LoopHalted("Agent decision budget exhausted")
                journal.begin("model")
                action = choose(history, limits.steps - len(decision_rows))
                journal.record(action, {"decision": True})
                continue
            if action.kind == "blocked":
                journal.record(action, {"blocked": True})
                journal.mark("blocked", "worker_reported_blocker")
                raise LoopHalted(
                    "Worker reported a blocker; inspect the saved decision"
                )
            journal.begin("finish" if action.kind == "finish" else "tool")
            previous = [s for s in history if not s["observation"].get("decision")]
            match = next(
                (s for s in previous if s["action"] == action.model_dump()), None
            )
            if match is not None and action.kind == "tool":
                repeats = 1
                for step in reversed(previous):
                    if not step["observation"].get("reused"):
                        break
                    repeats += 1
                journal.record(
                    action,
                    {
                        "reused": True,
                        "previous_step": match["number"],
                        "feedback": "This exact action already completed. No new tool call was made and no new evidence was obtained. Use its earlier observation; choose a different available action that addresses a remaining gap, finish from verified evidence, or report a blocker.",
                    },
                )
                if repeats >= limits.repeated_actions:
                    journal.mark("blocked", "repeated_actions")
                    raise LoopHalted(
                        "Agent repeated completed actions without progress"
                    )
                continue
            observation = finish(action) if action.kind == "finish" else execute(action)
            journal.record(action, observation)
            if action.kind == "finish":
                if observation.get("accepted") is not True:
                    continue
                journal.mark("ready", "investigation_complete")
                return observation
    except LoopHalted:
        raise
    except BaseException:
        journal.mark("blocked", "execution_failed_or_interrupted")
        raise
    finally:
        journal.add_elapsed(time.monotonic() - started)
