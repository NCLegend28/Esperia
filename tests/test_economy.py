"""Economy usage bounds, independent review integrity and cache invalidation."""

import json
from pathlib import Path
from typing import Any

import pytest

from esperia.economy import run_economy
from esperia.evidence import Source
from esperia.ledger import Ledger
from esperia.provider import Completion
from esperia.research import CHECKS


class Worker:
    """Deterministic test worker; never exposed through product CLI."""

    billing_mode = "subscription"

    def __init__(
        self, passed: bool = True, missing: bool = False, bad_quote: bool = False
    ):
        self.calls = 0
        self.passed, self.missing, self.bad_quote = passed, missing, bad_quote

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        self.calls += 1
        kind = json.loads(prompt)["output_schema"]["title"]
        body: dict[str, Any]
        if kind == "Analysis":
            body = {
                "claims": [
                    {
                        "statement": "Test fact",
                        "source_id": "S1",
                        "quote": (
                            "Fabricated quote with no support."
                            if self.bad_quote
                            else "The company reported revenue of ten dollars."
                        ),
                    }
                ],
                "draft": {
                    "title": "Report",
                    "sections": [
                        {
                            "title": "Analysis",
                            "text": "Test prose",
                            "source_ids": ["S1"],
                        }
                    ],
                    "missing_evidence": [],
                },
            }
        else:
            body = {
                "checks": [
                    {"name": name, "passed": self.passed, "explanation": "Test check"}
                    for name in CHECKS
                ],
                "corrections": [] if self.passed else ["Fix wording"],
                "needs_new_evidence": self.missing,
            }
        return Completion(json.dumps(body), 100, 100, f"test-{self.calls}", True)


def execute(
    folder: Path,
    worker: Worker,
    question: str = "Research",
    reviewer: Worker | None = None,
) -> tuple[Path, Ledger]:
    ledger = Ledger(folder / "jobs.sqlite", 0)
    job = ledger.create_subscription(question, 3)
    source = Source(
        id="S1",
        url="https://www.ionq.com/",
        fetched_at="2026-09-13T00:00:00Z",
        sha256="a" * 64,
        text="The company reported revenue of ten dollars.",
        truncated=False,
    )
    report = run_economy(
        ledger,
        worker,
        job,
        question,
        [source],
        folder / job,
        lambda _: None,
        reviewer=reviewer,
    )
    return report, ledger


def test_unchanged_rerun_uses_no_additional_calls(tmp_path: Path) -> None:
    worker = Worker()
    execute(tmp_path, worker)
    assert worker.calls == 2
    execute(tmp_path, worker)
    assert worker.calls == 2
    execute(tmp_path, worker, "Changed question")
    assert worker.calls == 4


def test_missing_evidence_stops_without_revision(tmp_path: Path) -> None:
    worker = Worker(passed=False, missing=True)
    report, _ = execute(tmp_path, worker)
    assert worker.calls == 2
    assert "new evidence" in report.read_text()


def test_revision_is_not_claimed_as_independently_reviewed(tmp_path: Path) -> None:
    worker = Worker(passed=False)
    report, ledger = execute(tmp_path, worker)
    assert worker.calls == 3
    assert "independent re-review pending" in report.read_text()
    assert ledger.list_jobs()[0]["state"] == "blocked"


def test_separate_reviewer_gets_only_one_call(tmp_path: Path) -> None:
    worker, reviewer = Worker(), Worker()
    execute(tmp_path, worker, reviewer=reviewer)
    assert worker.calls == 1 and reviewer.calls == 1


def test_bad_quote_never_cached(tmp_path: Path) -> None:
    worker = Worker(bad_quote=True)
    with pytest.raises(ValueError):
        execute(tmp_path, worker)
    assert not list((tmp_path / "cache").glob("*.json"))


def test_bad_quote_has_diagnostic_and_preserves_response(tmp_path: Path) -> None:
    worker = Worker(bad_quote=True)
    with pytest.raises(ValueError, match="Claim 1: quote is not verbatim in S1"):
        execute(tmp_path, worker)
    artifacts = list(tmp_path.glob("*/analysis-validation.json"))
    assert len(artifacts) == 1
    diagnostic = json.loads(artifacts[0].read_text())
    assert diagnostic["automatic_retry"] is False
    assert "Fabricated quote" not in artifacts[0].read_text()
    assert (artifacts[0].parent / "analysis.json").exists()
    assert worker.calls == 1
    assert Ledger(tmp_path / "jobs.sqlite", 0).list_jobs()[0]["state"] == "blocked"


def test_cross_company_quote_is_not_reassigned(tmp_path: Path) -> None:
    from esperia.execution import OutputValidationError

    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Compare", 3)
    sources = [
        Source(
            id=f"S{i}",
            url="https://www.ionq.com/",
            fetched_at="2026-09-13T00:00:00Z",
            sha256="a" * 64,
            text=text,
            truncated=False,
        )
        for i, text in enumerate(
            [
                "Different company has insufficient information.",
                "The company reported revenue of ten dollars.",
            ],
            1,
        )
    ]
    worker = Worker()
    with pytest.raises(OutputValidationError, match="quote occurs in S2"):
        run_economy(ledger, worker, job, "Compare", sources, tmp_path / job)
    assert worker.calls == 1
    assert not list((tmp_path / "cache").glob("*.json"))


def test_invalid_schema_redacts_model_output(tmp_path: Path) -> None:
    from esperia.economy import Analysis
    from esperia.execution import OutputValidationError, StageRunner

    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Test", 3)
    runner = StageRunner(ledger, Worker(), job, tmp_path, "", lambda _: None)
    with pytest.raises(OutputValidationError, match="required JSON schema") as error:
        runner.validate_output(
            "analysis", '{"unexpected":"private-value"}', True, Analysis, None
        )
    assert "private-value" not in str(error.value)
    assert "private-value" not in (tmp_path / "analysis-validation.json").read_text()


def test_incomplete_response_explained(tmp_path: Path) -> None:
    from esperia.economy import Analysis
    from esperia.execution import OutputValidationError, StageRunner

    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Test", 3)
    runner = StageRunner(ledger, Worker(), job, tmp_path, "", lambda _: None)
    with pytest.raises(OutputValidationError, match="response incomplete"):
        runner.validate_output("analysis", "", False, Analysis, None)
