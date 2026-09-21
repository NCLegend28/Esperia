"""Unassigned repair verdicts cannot contaminate report follow-ups."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_economy import Worker, execute

from esperia.economy import review_schema
from esperia.execution import OutputValidationError
from esperia.provider import Completion


@pytest.mark.parametrize("assignments", [None, []])
def test_no_assignments_forbid_repair_checks(assignments) -> None:
    schema = review_schema(assignments)
    body = {"checks": [], "corrections": [], "needs_new_evidence": False}
    assert schema.model_validate(body).repair_checks == []
    assert schema.model_json_schema()["properties"]["repair_checks"]["maxItems"] == 0
    with pytest.raises(ValidationError):
        schema.model_validate(
            {
                **body,
                "repair_checks": [
                    {"id": "C1", "passed": False, "explanation": "Invented"}
                ],
            }
        )


def test_assigned_repair_choices_are_dynamic() -> None:
    schema = review_schema([{"id": "task-42"}]).model_json_schema()
    assert schema["$defs"]["RepairCheck"]["properties"]["id"]["enum"] == ["task-42"]
    assert schema["properties"]["repair_checks"]["minItems"] == 1
    assert schema["properties"]["repair_checks"]["maxItems"] == 1


def test_unassigned_verdict_blocks_before_followups(tmp_path: Path) -> None:
    class UnassignedWorker(Worker):
        def complete(self, model, instructions, prompt, maximum):
            response = super().complete(model, instructions, prompt, maximum)
            if json.loads(prompt)["output_schema"]["title"] == "EconomyReview":
                body = json.loads(response.text)
                body["repair_checks"] = [
                    {"id": "C1", "passed": False, "explanation": "Invented"}
                ]
                return Completion(json.dumps(body), 100, 100, "review", True)
            return response

    worker = UnassignedWorker()
    with pytest.raises(OutputValidationError, match="repair_checks"):
        execute(tmp_path, worker)
    assert worker.calls == 2
    assert not list(tmp_path.glob("*/report.md"))
    assert not list(tmp_path.glob("*/followups.json"))
    assert list(tmp_path.glob("*/review-validation.json"))


def test_assigned_checks_are_required_in_generation_schema() -> None:
    schema = review_schema([{"id": "R1"}], ["scope", "citations"]).model_json_schema()
    assert "repair_checks" in schema["required"]
    assert schema["$defs"]["Check"]["properties"]["name"]["enum"] == [
        "scope",
        "citations",
    ]
    assert schema["properties"]["checks"]["minItems"] == 2
    assert schema["properties"]["checks"]["maxItems"] == 2
    with pytest.raises(ValidationError):
        review_schema([{"id": "R1"}]).model_validate(
            {"checks": [], "corrections": [], "needs_new_evidence": True}
        )
