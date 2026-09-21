"""Tool permission, accounting, interruption and output-bound regressions."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from esperia.tools import ToolError, ToolRegistry, ToolRuntime


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


def setup_runtime(
    path: Path, calls: list[str], *, fail: bool = False, output_bytes: int = 1000
) -> ToolRuntime:
    registry = ToolRegistry()

    def execute(request: Request) -> Result:
        calls.append(request.query)
        if fail:
            raise TimeoutError("sensitive provider detail")
        return Result(value=request.query)

    registry.register("search", "Read-only fixture", Request, Result, execute)
    return ToolRuntime(
        registry, frozenset({"search"}), path, max_calls=1, output_bytes=output_bytes
    )


@pytest.mark.parametrize(
    "name,args",
    [
        ("shell", {"query": "ok"}),
        ("search", {"query": 1}),
        ("search", {"query": "ok", "endpoint": "http://private"}),
    ],
)
def test_rejected_arguments_and_grants_do_not_execute(
    tmp_path: Path, name: str, args: dict[str, Any]
) -> None:
    calls: list[str] = []
    runtime = setup_runtime(tmp_path, calls)
    with pytest.raises(ToolError):
        runtime.invoke(name, args)
    assert calls == []
    with sqlite3.connect(runtime.path) as db:
        assert db.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 0


def test_tool_budget_is_shared_across_runtime_instances(tmp_path: Path) -> None:
    calls: list[str] = []
    first = setup_runtime(tmp_path, calls)
    assert first.invoke("search", {"query": "energy"}) == {"value": "energy"}
    second = setup_runtime(tmp_path, calls)
    with pytest.raises(ToolError, match="budget"):
        second.invoke("search", {"query": "science"})
    assert calls == ["energy"]
    with sqlite3.connect(first.path) as db:
        state, result = db.execute("SELECT state,result FROM calls").fetchone()
    assert state == "completed"
    assert "energy" in result


@pytest.mark.parametrize("state", ["running", "failed"])
def test_interrupted_or_failed_call_never_replays(tmp_path: Path, state: str) -> None:
    calls: list[str] = []
    runtime = setup_runtime(tmp_path, calls)
    with sqlite3.connect(runtime.path) as db:
        db.execute(
            "INSERT INTO calls (id,name,arguments,state,started_at) VALUES (?,?,?,?,?)",
            ("old", "search", "{}", state, "now"),
        )
    with pytest.raises(ToolError, match="inspection"):
        setup_runtime(tmp_path, calls).invoke("search", {"query": "energy"})
    assert not calls


def test_failure_is_recorded_without_leaking_raw_exception(tmp_path: Path) -> None:
    calls: list[str] = []
    runtime = setup_runtime(tmp_path, calls, fail=True)
    with pytest.raises(ToolError) as error:
        runtime.invoke("search", {"query": "energy"})
    assert "sensitive" not in str(error.value)
    with sqlite3.connect(runtime.path) as db:
        assert db.execute("SELECT state,code,result FROM calls").fetchone() == (
            "failed",
            "tool_execution_failed",
            None,
        )
    with pytest.raises(ToolError):
        runtime.invoke("search", {"query": "energy"})
    assert calls == ["energy"]


def test_output_overflow_never_becomes_success(tmp_path: Path) -> None:
    runtime = setup_runtime(tmp_path, [], output_bytes=10)
    with pytest.raises(ToolError):
        runtime.invoke("search", {"query": "x" * 20})
    with sqlite3.connect(runtime.path) as db:
        assert db.execute("SELECT state,result FROM calls").fetchone() == (
            "failed",
            None,
        )


def test_invalid_constructed_output_is_revalidated(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(
        "bad", "fixture", Request, Result, lambda _: Result.model_construct(value=123)
    )
    runtime = ToolRuntime(registry, frozenset({"bad"}), tmp_path, max_calls=1)
    with pytest.raises(ToolError):
        runtime.invoke("bad", {"query": "energy"})
    with sqlite3.connect(runtime.path) as db:
        assert db.execute("SELECT state,result FROM calls").fetchone() == (
            "failed",
            None,
        )


def test_concurrent_dispatch_cannot_bypass_reservation(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    entered, release = Event(), Event()
    registry = ToolRegistry()

    def run(request: Request) -> Result:
        entered.set()
        assert release.wait(5)
        return Result(value=request.query)

    registry.register("search", "fixture", Request, Result, run)
    first = ToolRuntime(registry, frozenset({"search"}), tmp_path, max_calls=1)
    second = ToolRuntime(registry, frozenset({"search"}), tmp_path, max_calls=1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(first.invoke, "search", {"query": "energy"})
        try:
            assert entered.wait(5)
            with pytest.raises(ToolError, match="inspection"):
                second.invoke("search", {"query": "science"})
        finally:
            release.set()
        assert future.result() == {"value": "energy"}
