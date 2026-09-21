"""Archive-specific citation choices cover drafts, excerpts and revisions."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_economy import Worker
from test_research import ScriptedProvider, source

from esperia.citations import citation_schema
from esperia.economy import SelectedAnalysis, run_economy
from esperia.ledger import Ledger
from esperia.research import Draft, SelectedNotes, run_research


def enums(schema: dict[str, Any], field: str) -> list[list[str]]:
    """Find enums for a named property, including nested model definitions."""
    found = []
    for name, prop in schema.get("properties", {}).items():
        if name == field:
            found.append(prop.get("items", prop)["enum"])
    for definition in schema.get("$defs", {}).values():
        found.extend(enums(definition, field))
    return found


@pytest.mark.parametrize("bad", ["S1:E25", "R1", "S2"])
def test_excerpt_or_invented_id_cannot_be_a_section_source(bad: str) -> None:
    bound = citation_schema(
        SelectedAnalysis, source_ids=["S1", "S3", "S4"], excerpt_ids=["S1:E25"]
    )
    body = {
        "claims": [{"statement": "Supported", "excerpt_id": "S1:E25"}],
        "draft": {
            "title": "Report",
            "sections": [{"title": "Section", "text": "Text", "source_ids": [bad]}],
            "missing_evidence": [],
        },
    }
    with pytest.raises(ValidationError):
        bound.model_validate(body)
    body["draft"]["sections"][0]["source_ids"] = ["S4"]
    bound.model_validate(body)
    schema = bound.model_json_schema()
    assert enums(schema, "source_ids") == [["S1", "S3", "S4"]]
    assert enums(schema, "excerpt_id") == [["S1:E25"]]
    assert schema["title"] == "SelectedAnalysis"


def test_schemas_are_isolated_and_keep_bounds() -> None:
    first = citation_schema(Draft, source_ids=["S1"])
    second = citation_schema(Draft, source_ids=["S4"])
    assert enums(first.model_json_schema(), "source_ids") == [["S1"]]
    assert enums(second.model_json_schema(), "source_ids") == [["S4"]]
    assert "enum" not in json.dumps(Draft.model_json_schema())
    sections = first.model_json_schema()["properties"]["sections"]
    assert sections["minItems"] == 1 and sections["maxItems"] == 12
    empty = citation_schema(SelectedNotes, source_ids=[], excerpt_ids=[])
    empty.model_validate({"claims": [], "limitations": ["No evidence"]})
    with pytest.raises(ValidationError):
        empty.model_validate(
            {"claims": [{"statement": "X", "excerpt_id": "S1:E1"}], "limitations": []}
        )


@pytest.mark.parametrize("mode", ["economy", "deep"])
def test_all_report_calls_receive_bound_schemas(tmp_path: Path, mode: str) -> None:
    worker = (
        Worker(passed=False) if mode == "economy" else ScriptedProvider(passed=False)
    )
    original = worker.complete
    captured = []

    def complete(model: str, instructions: str, prompt: str, maximum: int):
        schema = json.loads(prompt)["output_schema"]
        title = schema["title"]
        if title in {"SelectedAnalysis", "Draft"}:
            assert enums(schema, "source_ids") == [["S1"]]
            captured.append(title)
        if title in {"SelectedAnalysis", "SelectedNotes"}:
            assert all(
                value.startswith("S1:E") for value in enums(schema, "excerpt_id")[0]
            )
        return original(model, instructions, prompt, maximum)

    worker.complete = complete
    ledger = Ledger(tmp_path / "jobs.sqlite", 6500)
    job = (
        ledger.create_subscription("Research", 3)
        if mode == "economy"
        else ledger.create("Research", 500)
    )
    run = run_economy if mode == "economy" else run_research
    report = run(
        ledger, worker, job, "Research", [source()], tmp_path / "run", lambda _: None
    )
    assert report.exists()
    assert len(captured) == (2 if mode == "economy" else 3)
