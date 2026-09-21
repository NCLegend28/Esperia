"""Regressions for the user's rejected R1/R4 handoff and missing temporal context."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_agent_workflow import AgentWorker, actions, setup

from esperia.agent_loop import Journal
from esperia.agent_workflow import resume_agent, start_agent
from esperia.execution import OutputValidationError
from esperia.investigation import decision_schema


def test_last_turn_schema_only_offers_verified_source_ids() -> None:
    schema = decision_schema(2, 0, 1, [], ["S1", "S4"])
    generated = schema.model_json_schema()
    choices = generated["$defs"]["VerifiedFinishDecision"]["properties"]["source_ids"]
    assert choices["items"]["enum"] == ["S1", "S4"]
    assert choices["maxItems"] == 2
    bad = {**actions()[-1], "source_ids": ["R1", "R4"]}
    with pytest.raises(ValidationError):
        schema.model_validate({"decision": bad})
    good = {**actions()[-1], "source_ids": ["S1", "S4"]}
    assert schema.model_validate({"decision": good})


def test_no_sources_means_no_finish_even_on_last_turn() -> None:
    schema = decision_schema(0, 0, 1, [], [])
    with pytest.raises(ValidationError):
        schema.model_validate({"decision": actions()[-1]})
    assert schema.model_validate(
        {"decision": {"action": "blocked", "reason": "No verified evidence"}}
    )


@pytest.mark.parametrize("ids", [["S9"], ["S1", "S1"]])
def test_independent_gate_rejects_invented_or_duplicate_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ids: list[str]
) -> None:
    settings, ledger = setup(tmp_path, monkeypatch)
    decisions = actions()
    decisions[-1]["source_ids"] = ids
    worker = AgentWorker(decisions, settings.research_root)
    with pytest.raises(OutputValidationError):
        start_agent(
            ledger,
            settings,
            "Research next 5 years",
            "ollama",
            "economy",
            None,
            lambda *_: (worker, None),
            lambda _: None,
        )
    assert not list(settings.research_root.glob("*/report.md"))


def test_timeframe_saved_in_request_decisions_handoff_and_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, ledger = setup(tmp_path, monkeypatch)
    worker = AgentWorker(actions(), settings.research_root, "SelectedAnalysis")
    job = start_agent(
        ledger,
        settings,
        "Compare energy over the next 5 years",
        "ollama",
        "economy",
        None,
        lambda *_: (worker, None),
        lambda _: None,
    )
    root = settings.research_root / job
    request = json.loads((root / "request.json").read_text())
    anchor = request["timeframe"]
    assert anchor["requested_horizon"]["years"] == 5
    assert all(task["timeframe"] == anchor for task in worker.inputs)
    assert json.loads((root / "source-scope.json").read_text())["timeframe"] == anchor
    resume_agent(ledger, settings, job, lambda *_: (worker, None), lambda _: None)
    assert Journal(root).snapshot()["request"]["timeframe"] == anchor
    assert ledger.review_record(job)["job"]["state"] == "awaiting_owner"
