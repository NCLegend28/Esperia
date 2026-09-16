"""Repair dispatch, task review gates, lineage and duplicate protection."""

import json
from pathlib import Path

import pytest
from test_economy import Worker

from esperia.evidence import Source
from esperia.execution import OutputValidationError
from esperia.ledger import Ledger, PolicyError
from esperia.provider import Completion
from esperia.repair import plan_repair, run_repair


class RepairWorker(Worker):
    def __init__(self, resolved: bool = True, omit: bool = False):
        super().__init__()
        self.resolved, self.omit = resolved, omit

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        result = super().complete(model, instructions, prompt, maximum)
        body = json.loads(result.text)
        if "checks" in body:
            tasks = json.loads(json.loads(prompt)["task"])["assigned_repairs"]
            body["repair_checks"] = (
                []
                if self.omit
                else [
                    {
                        "id": t["id"],
                        "passed": self.resolved,
                        "explanation": "Evidence evaluated",
                    }
                    for t in tasks
                ]
            )
        return Completion(json.dumps(body), 100, 100, result.response_id, True)


def parent(root: Path) -> tuple[Ledger, str]:
    ledger = Ledger(root / "jobs.sqlite", 0)
    job = ledger.create_subscription("Original question", 3)
    ledger.start(job)
    ledger.complete_research(job, False)
    folder = root / job
    folder.mkdir()
    (folder / "analysis-validation.json").write_text(
        json.dumps({"issues": ["Claim 5: S5 quote belongs to S6"]})
    )
    return ledger, job


def source() -> Source:
    return Source(
        id="S1",
        url="https://www.ionq.com/",
        fetched_at="2026-09-15T00:00:00Z",
        sha256="a" * 64,
        text="The company reported revenue of ten dollars.",
        truncated=False,
    )


def test_plan_includes_validation_and_makes_no_child(tmp_path: Path) -> None:
    ledger, job = parent(tmp_path)
    plan = plan_repair(ledger, tmp_path, job)
    assert plan["tasks"][0]["assignee"] == "corrector"
    assert "S5" in plan["tasks"][0]["detail"]
    assert len(ledger.list_jobs()) == 1


def test_repair_has_fresh_review_and_durable_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("esperia.repair.collect", lambda urls, output: [source()])
    ledger, job = parent(tmp_path)
    worker = RepairWorker()
    report = run_repair(ledger, tmp_path, job, worker, None, "ollama", [source().url])
    assert worker.calls == 2
    child = report.parent.name
    assert ledger.review_record(job)["job"]["state"] == "blocked"
    assert ledger.review_record(child)["job"]["state"] == "awaiting_owner"
    reopened = Ledger(ledger.path, 0)
    assert reopened.repair_record(child)["parent_id"] == job
    assert reopened.repair_record(child)["tasks"][0]["state"] == "review_passed"
    assert child in reopened.repair_record(job)["children"]
    with pytest.raises(PolicyError, match="already dispatched"):
        run_repair(ledger, tmp_path, job, worker, None, "ollama", [source().url])
    assert worker.calls == 2


def test_failed_task_cannot_pass_even_when_general_checks_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("esperia.repair.collect", lambda urls, output: [source()])
    ledger, job = parent(tmp_path)
    report = run_repair(
        ledger,
        tmp_path,
        job,
        RepairWorker(resolved=False),
        None,
        "ollama",
        [source().url],
    )
    assert ledger.review_record(report.parent.name)["job"]["state"] == "blocked"
    assert ledger.repair_record(report.parent.name)["tasks"][0]["state"] == "blocked"
    assert "repair_reviewer" in report.read_text()


def test_omitted_task_verdict_blocks_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("esperia.repair.collect", lambda urls, output: [source()])
    ledger, job = parent(tmp_path)
    with pytest.raises(OutputValidationError, match="every assigned"):
        run_repair(
            ledger,
            tmp_path,
            job,
            RepairWorker(omit=True),
            None,
            "ollama",
            [source().url],
        )
    child = ledger.repair_record(job)["children"][0]
    assert ledger.repair_record(child)["tasks"][0]["state"] == "blocked"
    assert ledger.review_record(child)["report"] is None


def test_collection_failure_retains_blocked_assignments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failure(urls: list[str], output: Path) -> list[Source]:
        raise ValueError("No source")

    monkeypatch.setattr("esperia.repair.collect", failure)
    ledger, job = parent(tmp_path)
    worker = RepairWorker()
    with pytest.raises(ValueError):
        run_repair(ledger, tmp_path, job, worker, None, "ollama", [source().url])
    child = ledger.repair_record(job)["children"][0]
    assert ledger.review_record(child)["job"]["state"] == "cancelled"
    assert ledger.repair_record(child)["tasks"][0]["state"] == "blocked"
    assert worker.calls == 0


def test_uncertain_parent_cannot_dispatch(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Unknown outcome", 3)
    ledger.start(job)
    call = ledger.reserve_subscription_call(job, "analysis", "local")
    ledger.uncertain_call(call)
    ledger.block_research(job)
    with pytest.raises(PolicyError, match="uncertain"):
        plan_repair(ledger, tmp_path, job)


def test_invalid_source_refused_before_child_creation(tmp_path: Path) -> None:
    ledger, job = parent(tmp_path)
    with pytest.raises(ValueError):
        run_repair(
            ledger,
            tmp_path,
            job,
            RepairWorker(),
            None,
            "ollama",
            ["http://localhost/secrets"],
        )
    assert len(ledger.list_jobs()) == 1
