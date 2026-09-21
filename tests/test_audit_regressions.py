"""Regression checks for coverage gates, deep budgets and repairable validation."""

import json
from pathlib import Path
from typing import Any

import pytest
from test_economy import Worker
from test_research import ScriptedProvider, source

from esperia.economy import run_economy
from esperia.execution import OutputValidationError
from esperia.ledger import Ledger, PolicyError
from esperia.owner import inspect_job
from esperia.provider import Completion
from esperia.repair import plan_repair
from esperia.research import run_research


class DeepWorker(ScriptedProvider):
    """Subscription fake supporting multiple sources and malformed stage output."""

    billing_mode = "subscription"

    def __init__(self, defect: str = "", passed: bool = True):
        super().__init__(passed=passed)
        self.defect = defect
        self.tasks: list[dict[str, Any]] = []

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        result = super().complete(model, instructions, prompt, maximum)
        request = json.loads(prompt)
        task = json.loads(request["task"])
        self.tasks.append(task)
        kind = request["output_schema"]["title"]
        body = json.loads(result.text)
        if kind == "SelectedNotes":
            body["claims"][0]["excerpt_id"] = task["excerpts"][0]["id"]
            if self.defect == "quote":
                body["claims"][0]["excerpt_id"] = "invented"
            elif self.defect == "source":
                body["claims"][0]["excerpt_id"] = "S99:E1"
        if kind == "Draft" and (
            self.defect == "draft" or (self.defect == "revision" and "draft" in task)
        ):
            body["sections"][0]["source_ids"] = ["S99"]
        if kind == "Review" and self.defect == "review":
            body["checks"] = body["checks"][:-1]
        return Completion(json.dumps(body), 100, 100, result.response_id, True)


@pytest.mark.parametrize("mode", ["economy", "deep"])
@pytest.mark.parametrize("missing", [True, False])
def test_seed_coverage_gate_and_repair(
    tmp_path: Path, mode: str, missing: bool
) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Compare", 8)
    folder = tmp_path / job
    (folder / "evidence").mkdir(parents=True)
    coverage = {
        "seeds": ["https://www.ionq.com/", "https://investors.rigetti.com/"],
        "seed_coverage": {
            "https://www.ionq.com/": 1,
            "https://investors.rigetti.com/": 0 if missing else 1,
        },
        "documents": 1,
        "requests": 2,
        "limits": {},
        "events": [],
    }
    (folder / "evidence/discovery.json").write_text(json.dumps(coverage))
    provider = DeepWorker() if mode == "deep" else Worker()
    run = run_research if mode == "deep" else run_economy
    run(ledger, provider, job, "Compare", [source()], folder, lambda _: None)
    record = inspect_job(ledger, tmp_path, job)
    assert record["can_accept"] is (not missing)
    if mode == "deep":
        assert isinstance(provider, DeepWorker)
        assert (
            provider.tasks[-1]["collection_coverage"]["seed_coverage"]
            == coverage["seed_coverage"]
        )
    if missing:
        with pytest.raises(PolicyError):
            ledger.decide_report(job, record["report"]["sha256"], "accepted")
        assert any(
            "rigetti" in t["detail"]
            for t in plan_repair(ledger, tmp_path, job)["tasks"]
        )
    else:
        ledger.decide_report(job, record["report"]["sha256"], "accepted")


@pytest.mark.parametrize(
    "defect,stage",
    [
        ("quote", "evidence-S1-selection"),
        ("source", "evidence-S1-selection"),
        ("draft", "draft"),
        ("review", "review-0"),
        ("revision", "revision-1"),
    ],
)
def test_semantic_errors_become_repair_tasks(
    tmp_path: Path, defect: str, stage: str
) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Research", 8)
    folder = tmp_path / job
    with pytest.raises(OutputValidationError):
        run_research(
            ledger,
            DeepWorker(defect, passed=False),
            job,
            "Research",
            [source()],
            folder,
            lambda _: None,
        )
    assert (folder / f"{stage}.json").is_file()
    assert (folder / f"{stage}-validation.json").is_file()
    assert all(c["state"] == "settled" for c in ledger.list_calls(job))
    assert not inspect_job(ledger, tmp_path, job)["can_accept"]
    assert plan_repair(ledger, tmp_path, job)["tasks"]


def test_insufficient_deep_budget_stops_before_generation(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Research", 16)
    worker = DeepWorker()
    sources = [source().model_copy(update={"id": f"S{i}"}) for i in range(1, 19)]
    with pytest.raises(PolicyError, match="at least 21 calls"):
        run_research(
            ledger, worker, job, "Research", sources, tmp_path / job, lambda _: None
        )
    assert worker.calls == 0
    assert ledger.list_calls(job) == []
    assert ledger.review_record(job)["job"]["state"] == "cancelled"


@pytest.mark.parametrize("count", [18, 24])
def test_deep_default_sized_budget_finishes_full_revision_cycle(
    tmp_path: Path, count: int
) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Research", 31)
    worker = DeepWorker(passed=False)
    sources = [source().model_copy(update={"id": f"S{i}"}) for i in range(1, count + 1)]
    report = run_research(
        ledger, worker, job, "Research", sources, tmp_path / job, lambda _: None
    )
    assert report.is_file()
    assert worker.calls == count + 7
    assert (report.parent / "review-2.json").is_file()


def test_minimum_cap_saves_failed_review_without_unreviewable_revision(
    tmp_path: Path,
) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Research", 4)
    worker = DeepWorker(passed=False)
    report = run_research(
        ledger, worker, job, "Research", [source()], tmp_path / job, lambda _: None
    )
    assert report.is_file()
    assert worker.calls == 4
    assert not (report.parent / "revision-1.json").exists()
    assert plan_repair(ledger, tmp_path, job)["tasks"]


def test_cli_default_budget_handles_discovery_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from esperia import cli

    class ConsoleWorker(DeepWorker):
        def close(self) -> None:
            pass

    worker = ConsoleWorker()
    sources = [source().model_copy(update={"id": f"S{i}"}) for i in range(1, 19)]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ESPERIA_DATABASE", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setattr(
        "sys.argv",
        ["esperia", "research", "Compare", "--mode", "deep", "--sources", "seeds.json"],
    )
    monkeypatch.setattr(cli, "research_providers", lambda *args: (worker, None))
    monkeypatch.setattr(cli, "load_manifest", lambda _: [source().url])
    monkeypatch.setattr(cli, "discover", lambda *args, **kwargs: sources)
    cli.main()
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.list_jobs()[0]
    assert worker.calls == 21
    assert job["state"] == "awaiting_owner"
    assert ledger.remaining_subscription_calls(job["id"]) == 4


def test_omitted_seed_count_blocks_coverage() -> None:
    from esperia.coverage import coverage_tasks

    tasks = coverage_tasks(
        {
            "seeds": ["https://www.ionq.com/", "https://ir.arqit.uk/"],
            "seed_coverage": {"https://www.ionq.com/": 1},
        }
    )
    assert len(tasks) == 1
    assert "arqit" in tasks[0].detail
