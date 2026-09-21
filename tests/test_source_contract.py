"""Regression for mixed search/finish decisions and safe schema diagnostics."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_tool_sourcing import DecisionWorker, action, finish

from esperia.execution import OutputValidationError, StageRunner, schema_issues
from esperia.ledger import Ledger
from esperia.sourcing import SourceAction


def test_mixed_action_is_rejected_with_actionable_safe_diagnostic(
    tmp_path: Path,
) -> None:
    mixed = action()
    mixed["selections"] = finish()["selections"]
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("schema regression", 2)
    runner = StageRunner(
        ledger, DecisionWorker([]), job, tmp_path, "system", lambda _: None
    )
    with pytest.raises(OutputValidationError, match="selections.*too_long"):
        runner.validate_output(
            "source-step-3", json.dumps({"decision": mixed}), True, SourceAction, None
        )
    diagnostic = json.loads((tmp_path / "source-step-3-validation.json").read_text())
    assert diagnostic["automatic_retry"] is False
    assert "selections" in diagnostic["issues"][0]
    assert "too_long" in diagnostic["issues"][0]


@pytest.mark.parametrize("payload", [action(), finish()])
def test_valid_single_action_round_trips_inside_envelope(payload: dict) -> None:
    decision = SourceAction.model_validate({"decision": payload})
    assert decision.model_dump()["decision"] == payload


def test_generation_schema_excludes_mixed_actions() -> None:
    # The regression was an after-validator absent from the schema sent to Ollama.
    schema = SourceAction.model_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    branches = [
        schema["$defs"][branch["$ref"].rsplit("/", 1)[-1]]
        for branch in schema["properties"]["decision"]["anyOf"]
    ]
    search = next(
        branch
        for branch in branches
        if branch["properties"]["action"]["const"] == "tool"
    )
    finish_branch = next(
        branch
        for branch in branches
        if branch["properties"]["action"]["const"] == "finish"
    )
    assert search["properties"]["selections"]["maxItems"] == 0
    assert finish_branch["properties"]["tool"]["type"] == "null"
    assert finish_branch["properties"]["arguments"]["type"] == "null"
    assert finish_branch["properties"]["selections"]["minItems"] == 1


def test_diagnostics_exclude_unknown_keys_and_model_values() -> None:
    payload = finish()
    payload["private-key-from-response"] = "secret response value"
    payload["tool"] = "secret tool value"
    try:
        SourceAction.model_validate({"decision": payload})
    except ValidationError as error:
        diagnostic = json.dumps(schema_issues(error, SourceAction))
    else:
        pytest.fail("Invalid output was accepted")
    assert "private-key-from-response" not in diagnostic
    assert "secret" not in diagnostic
    assert "extra_forbidden" in diagnostic
    assert "none_required" in diagnostic
