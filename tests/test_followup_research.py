"""Targeted repair preserves lineage, budgets, provenance and pause checkpoints."""

import json

import pytest
from test_agent_workflow import AgentWorker, actions, archive, setup

from esperia.agent_loop import Journal
from esperia.agent_workflow import resume_agent
from esperia.evidence import load_archive
from esperia.followup_research import merge_evidence, run_followup
from esperia.ledger import PolicyError
from esperia.provider import Completion


class FollowupWorker(AgentWorker):
    def complete(self, model, instructions, prompt, maximum) -> Completion:
        result = super().complete(model, instructions, prompt, maximum)
        if json.loads(prompt)["output_schema"]["title"] == "EconomyReview":
            body = json.loads(result.text)
            tasks = json.loads(json.loads(prompt)["task"])["assigned_repairs"]
            body["repair_checks"] = [
                {"id": t["id"], "passed": True, "explanation": "Evidence reviewed"}
                for t in tasks
            ]
            return Completion(json.dumps(body), 1, 1, result.response_id, True)
        return result


def prepare(tmp_path, monkeypatch):
    settings, ledger = setup(tmp_path, monkeypatch)
    root = settings.research_root
    job = ledger.create_subscription("Original question", 2)
    ledger.start(job)
    folder = root / job
    folder.mkdir(parents=True)
    archive(["https://example.com/old"], "Original", folder / "evidence")
    (folder / "followups.json").write_text(
        json.dumps(
            {
                "status": "pending",
                "tasks": [
                    {
                        "origin": "draft",
                        "criterion": "missing_evidence",
                        "detail": "Missing primary forecasts",
                    }
                ],
            }
        )
    )
    timeframe = {
        "as_of_date": "2026-09-21",
        "requested_horizon": {"end_date": "2031-09-21"},
    }
    (folder / "request.json").write_text(
        json.dumps({"question": "Original question", "timeframe": timeframe})
    )
    report = folder / "report.md"
    report.write_text("Earlier draft with unresolved forecasts [S1].")
    ledger.complete_research(job, False, report)
    return settings, ledger, job, timeframe


def test_targeted_search_reuses_evidence_and_reviews_assignments(tmp_path, monkeypatch):
    settings, ledger, parent, timeframe = prepare(tmp_path, monkeypatch)
    worker = FollowupWorker(actions(), settings.research_root)
    child = run_followup(ledger, settings, parent, worker, None, "ollama")
    output = settings.research_root / child
    assert worker.calls == 5
    assert worker.inputs[0]["goal"] == "Original question"
    assert worker.inputs[0]["timeframe"] == timeframe
    assert (
        worker.inputs[0]["followup"]["tasks"][0]["detail"]
        == "Missing primary forecasts"
    )
    assert (
        "example.com/old" in worker.inputs[0]["followup"]["retained_sources"][0]["url"]
    )
    sources = load_archive(output / "report-evidence", settings)
    assert [s.id for s in sources] == ["S1", "S2"]
    assert [s.url for s in sources] == [
        "https://example.com/report",
        "https://example.com/old",
    ]
    assert json.loads((output / "previous-report.json").read_text())["text"].startswith(
        "Earlier draft"
    )
    assert ledger.review_record(child)["job"]["state"] == "awaiting_owner"
    assert ledger.repair_record(child)["tasks"][0]["state"] == "review_passed"
    assert ledger.review_record(parent)["job"]["state"] == "blocked"
    with pytest.raises(PolicyError, match="already dispatched"):
        run_followup(ledger, settings, parent, worker, None, "ollama")
    assert worker.calls == 5


@pytest.mark.parametrize("failure", ["budget", "archive", "report"])
def test_invalid_preconditions_do_not_dispatch(tmp_path, monkeypatch, failure):
    settings, ledger, parent, _ = prepare(tmp_path, monkeypatch)
    folder = settings.research_root / parent
    if failure == "archive":
        next((folder / "evidence").glob("*.source")).write_text("tampered")
    if failure == "report":
        (folder / "report.md").write_text("changed")
    worker = FollowupWorker(actions(), settings.research_root)
    with pytest.raises((ValueError, PolicyError)):
        run_followup(
            ledger,
            settings,
            parent,
            worker,
            None,
            "ollama",
            call_limit=2 if failure == "budget" else None,
        )
    assert worker.calls == 0
    assert len(ledger.list_jobs()) == 1


def test_followup_report_pause_resume_reuses_completed_analysis(tmp_path, monkeypatch):
    settings, ledger, parent, _ = prepare(tmp_path, monkeypatch)
    worker = FollowupWorker(
        actions(), settings.research_root, pause_stage="SelectedAnalysis"
    )
    child = run_followup(ledger, settings, parent, worker, None, "ollama")
    output = settings.research_root / child
    assert Journal(output).snapshot()["status"] == "paused"
    reviewer = FollowupWorker([], settings.research_root)
    reviewer.close = lambda: None
    resume_agent(ledger, settings, child, lambda *_: (reviewer, None), lambda _: None)
    assert reviewer.calls == 1
    assert ledger.review_record(child)["job"]["state"] == "awaiting_owner"
    assert ledger.repair_record(child)["tasks"][0]["state"] == "review_passed"


def test_evidence_merge_discloses_omissions_and_deduplicates(tmp_path, monkeypatch):
    settings, _ = setup(tmp_path, monkeypatch)
    archive(["https://example.com/new"], "new", tmp_path / "evidence")
    archive(["https://example.com/old"], "old", tmp_path / "prior-evidence")
    (tmp_path / "source-scope.json").write_text(
        json.dumps({"scope": "New", "limitations": []})
    )
    (tmp_path / "parent-scope.json").write_text(
        json.dumps({"limitations": ["Old gap"]})
    )
    settings = settings.model_copy(update={"max_seeds": 1})
    result = merge_evidence(tmp_path, settings)
    assert len(load_archive(result, settings)) == 1
    scope = json.loads((tmp_path / "source-scope.json").read_text())
    assert "Old gap" in scope["limitations"]
    assert any("example.com/old" in s for s in scope["limitations"])
    before = (result / "sources.json").read_bytes()
    assert (merge_evidence(tmp_path, settings) / "sources.json").read_bytes() == before


def test_followup_extraction_targets_saved_gaps(tmp_path, monkeypatch):
    settings, ledger, parent, _ = prepare(tmp_path, monkeypatch)
    queries = []

    def capture(urls, question, output, **kwargs):
        queries.append(question)
        return archive(urls, question, output, **kwargs)

    monkeypatch.setattr("esperia.investigation.discover", capture)
    worker = FollowupWorker(actions(), settings.research_root)
    run_followup(ledger, settings, parent, worker, None, "ollama")
    assert "Missing primary forecasts" in queries[0]


def test_failed_followup_review_keeps_child_blocked(tmp_path, monkeypatch):
    settings, ledger, parent, _ = prepare(tmp_path, monkeypatch)
    worker = FollowupWorker(actions(), settings.research_root)
    worker.passed = False
    child = run_followup(ledger, settings, parent, worker, None, "ollama")
    assert ledger.review_record(child)["job"]["state"] == "blocked"
    assert Journal(settings.research_root / child).snapshot()["status"] == "completed"
    assert len(ledger.repair_record(parent)["children"]) == 1
    assert len(ledger.repair_record(child)["children"]) == 0


def test_legacy_unassigned_repair_findings_are_not_dispatched(tmp_path, monkeypatch):
    from esperia.repair import plan_repair

    settings, ledger, parent, _ = prepare(tmp_path, monkeypatch)
    path = settings.research_root / parent / "followups.json"
    body = json.loads(path.read_text())
    body["tasks"].append(
        {
            "origin": "repair_reviewer",
            "criterion": "C1",
            "detail": "Invented assignment",
        }
    )
    path.write_text(json.dumps(body))
    assert len(plan_repair(ledger, settings.research_root, parent)["tasks"]) == 1
