"""Crash, pause, bounded progress and concurrency regressions without model spending."""

from pathlib import Path
from typing import Any

import pytest

from esperia.agent_loop import Action, Journal, LoopError, LoopHalted, run_loop
from esperia.settings import LoopSettings


def tool(query: str = "topic") -> Action:
    return Action(kind="tool", name="search", arguments={"query": query})


def finish() -> Action:
    return Action(kind="finish", name="finish", arguments={"sources": ["S1"]})


def setup(tmp_path: Path) -> Journal:
    journal = Journal(tmp_path)
    journal.create({"question": "A real goal"})
    return journal


def test_pause_after_model_resumes_saved_decision_without_repeating_it(
    tmp_path: Path,
) -> None:
    journal = setup(tmp_path)
    choices: list[int] = []
    executed: list[Action] = []

    def choose(history: list[dict[str, Any]], remaining: int) -> Action:
        choices.append(remaining)
        if len(choices) == 1:
            journal.control("pause")
            return tool()
        return finish()

    with pytest.raises(LoopHalted, match="paused"):
        run_loop(
            journal,
            choose,
            lambda a: executed.append(a) or {"evidence": True},
            lambda a: {"accepted": True},
            LoopSettings(),
        )
    assert not executed
    assert journal.snapshot()["pending"] is None
    journal.control("resume")
    result = run_loop(
        journal,
        choose,
        lambda a: executed.append(a) or {"evidence": True},
        lambda a: {"accepted": True},
        LoopSettings(),
    )
    assert result["accepted"]
    assert choices == [10, 9]
    assert executed == [tool()]


def test_repetition_stops_without_duplicate_dispatch(tmp_path: Path) -> None:
    journal = setup(tmp_path)
    executed: list[Action] = []
    with pytest.raises(LoopHalted, match="without progress"):
        run_loop(
            journal,
            lambda *_: tool(),
            lambda a: executed.append(a) or {"result": 1},
            lambda _: {},
            LoopSettings(repeated_actions=2),
        )
    assert len(executed) == 1
    assert journal.snapshot()["reason"] == "repeated_actions"
    assert journal.snapshot()["pending"] is None


def test_finish_is_a_gate_not_model_self_approval(tmp_path: Path) -> None:
    journal = setup(tmp_path)
    decisions = iter([finish(), tool(), finish()])
    checks = iter(
        [
            {"accepted": False, "feedback": "Need documentary evidence"},
            {"accepted": True},
        ]
    )
    assert run_loop(
        journal,
        lambda *_: next(decisions),
        lambda _: {"evidence": True},
        lambda _: next(checks),
        LoopSettings(),
    )["accepted"]
    assert len(journal.snapshot()["steps"]) == 6


def test_uncertain_work_is_never_replayed(tmp_path: Path) -> None:
    journal = setup(tmp_path)
    journal.begin("tool")
    with pytest.raises(LoopHalted, match="No replay"):
        run_loop(
            journal,
            lambda *_: pytest.fail("Repeated decision"),
            lambda _: pytest.fail("Repeated tool"),
            lambda _: {},
            LoopSettings(),
        )
    assert journal.snapshot()["status"] == "blocked"
    with pytest.raises(LoopError):
        journal.control("resume")


def test_stop_is_persistent_and_cannot_be_resumed(tmp_path: Path) -> None:
    journal = setup(tmp_path)
    journal.control("pause")
    journal.control("stop")
    with pytest.raises(LoopError):
        journal.control("resume")
    assert journal.snapshot()["status"] == "stopped"


def test_only_one_worker_can_own_a_run(tmp_path: Path) -> None:
    journal = setup(tmp_path)
    with journal.worker(), pytest.raises(LoopError, match="Another worker"):
        with Journal(tmp_path).worker():
            pytest.fail("Second worker entered")


def test_step_and_accumulated_time_limits(tmp_path: Path) -> None:
    journal = setup(tmp_path)
    with pytest.raises(LoopHalted, match="decision budget"):
        run_loop(
            journal,
            lambda history, _: tool(str(len(history))),
            lambda _: {},
            lambda _: {},
            LoopSettings(steps=3),
        )
    assert len(journal.snapshot()["steps"]) == 6
    other = setup(tmp_path / "time")
    other.add_elapsed(100)
    with pytest.raises(LoopHalted, match="time budget"):
        run_loop(
            other,
            lambda *_: pytest.fail("Budget ignored"),
            lambda _: {},
            lambda _: {},
            LoopSettings(seconds=50),
        )


def test_keyboard_interrupt_preserves_pending_outcome(tmp_path: Path) -> None:
    journal = setup(tmp_path)

    def execute(_: Action) -> dict[str, Any]:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_loop(journal, lambda *_: tool(), execute, lambda _: {}, LoopSettings())
    assert journal.snapshot()["pending"] == "tool"
    assert journal.snapshot()["status"] == "blocked"


def test_new_observation_resets_consecutive_repetition_counter(tmp_path: Path) -> None:
    journal = setup(tmp_path)
    decisions = iter([tool("one"), tool("one"), tool("two"), tool("two"), finish()])
    dispatched: list[Action] = []
    result = run_loop(
        journal,
        lambda *_: next(decisions),
        lambda a: dispatched.append(a) or {"new_observation": True},
        lambda _: {"accepted": True},
        LoopSettings(repeated_actions=2),
    )
    assert result["accepted"]
    assert dispatched == [tool("one"), tool("two")]
    reused = [
        step
        for step in journal.snapshot()["steps"]
        if step["observation"].get("reused")
    ]
    assert len(reused) == 2
    assert all(
        "different available action" in s["observation"]["feedback"] for s in reused
    )
