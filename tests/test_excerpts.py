"""Exact local citation selection and failure isolation without live model usage."""

import json
from pathlib import Path

import pytest
from test_economy import Worker, execute

from esperia.evidence import Source
from esperia.excerpts import excerpt_catalog
from esperia.execution import OutputValidationError
from esperia.provider import Completion


class LocalSelectionWorker(Worker):
    billing_mode = "local"

    def __init__(self, bad_ref: bool = False):
        super().__init__()
        self.bad_ref = bad_ref

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        data = json.loads(prompt)
        if data["output_schema"]["title"] != "SelectedAnalysis":
            return super().complete(model, instructions, prompt, maximum)
        task = json.loads(data["task"])
        data["output_schema"]["title"] = "Analysis"
        result = super().complete(model, instructions, json.dumps(data), maximum)
        body = json.loads(result.text)
        body["claims"] = [
            {
                "statement": "The company reported revenue of ten dollars.",
                "excerpt_id": "invented" if self.bad_ref else task["excerpts"][0]["id"],
            }
        ]
        assert (
            "quote" not in data["output_schema"]["$defs"]["SelectedClaim"]["properties"]
        )
        return Completion(json.dumps(body), 100, 100, result.response_id, True)


def test_local_selection_materializes_exact_quote_and_preserves_raw(
    tmp_path: Path,
) -> None:
    worker = LocalSelectionWorker()
    report, _ = execute(tmp_path, worker)
    assert worker.calls == 2
    raw = json.loads(
        json.loads((report.parent / "analysis-selection.json").read_text())["text"]
    )
    resolved = json.loads(
        json.loads((report.parent / "analysis.json").read_text())["text"]
    )
    assert "quote" not in raw["claims"][0]
    assert (
        resolved["claims"][0]["quote"] == "The company reported revenue of ten dollars."
    )
    assert resolved["claims"][0]["source_id"] == "S1"
    assert (report.parent / "excerpt-catalog.json").is_file()
    execute(tmp_path, worker)
    assert worker.calls == 2


def test_unknown_excerpt_fails_without_review_or_cache(tmp_path: Path) -> None:
    worker = LocalSelectionWorker(bad_ref=True)
    with pytest.raises(OutputValidationError, match=r"claims\.0\.excerpt_id"):
        execute(tmp_path, worker)
    assert worker.calls == 1
    assert not list((tmp_path / "cache").glob("*.json"))
    assert len(list(tmp_path.glob("*/analysis-selection-validation.json"))) == 1


@pytest.mark.parametrize("length", [20, 399, 400, 401, 500, 801, 12000])
def test_catalog_preserves_every_character_with_bounded_quotes(length: int) -> None:
    text = ("Source text with punctuation: $1.2; “quote”. " * 400)[:length]
    source = Source(
        id="S1",
        url="https://www.ionq.com/",
        fetched_at="2026-09-15T00:00:00Z",
        sha256="a" * 64,
        text=text,
        truncated=False,
    )
    catalog = excerpt_catalog([source])
    covered: set[int] = set()
    for excerpt in catalog.values():
        assert excerpt.source_id == "S1"
        assert excerpt.quote == text[excerpt.start : excerpt.end]
        assert 20 <= len(excerpt.quote) <= 500
        covered.update(range(excerpt.start, excerpt.end))
    assert covered == set(range(length))
