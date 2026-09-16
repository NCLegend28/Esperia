"""Verify owner decisions, immutable version binding, and consolidated review tasks."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from esperia.followups import build_followups, save_followups
from esperia.ledger import Ledger, PolicyError
from esperia.owner import inspect_job


def ready(root: Path, passed: bool = True) -> tuple[Ledger, str, Path, str]:
    ledger = Ledger(root / "jobs.sqlite", 0)
    job = ledger.create_subscription("Research", 3)
    ledger.start(job)
    report = root / job / "report.md"
    report.parent.mkdir()
    report.write_text("Reviewed report")
    ledger.complete_research(job, passed, report)
    digest = ledger.review_record(job)["report"]["sha256"]
    return ledger, job, report, digest


def test_accept_survives_restart_and_is_one_time(tmp_path: Path) -> None:
    ledger, job, _, digest = ready(tmp_path)
    assert inspect_job(ledger, tmp_path, job)["can_accept"]
    ledger.decide_report(job, digest, "accepted")
    reopened = Ledger(ledger.path, 0)
    record = reopened.review_record(job)
    assert record["job"]["state"] == "accepted"
    assert record["decision"]["report_sha256"] == digest
    assert record["decision"]["actor"] == "local_owner"
    with pytest.raises(PolicyError):
        reopened.decide_report(job, digest, "accepted")


def test_changed_report_or_stale_digest_cannot_be_accepted(tmp_path: Path) -> None:
    ledger, job, report, digest = ready(tmp_path)
    with pytest.raises(PolicyError, match="version"):
        ledger.decide_report(job, "0" * 64, "accepted")
    report.write_text("Changed after review")
    with pytest.raises(PolicyError, match="changed"):
        ledger.decide_report(job, digest, "accepted")
    assert not inspect_job(ledger, tmp_path, job)["can_accept"]
    assert ledger.review_record(job)["decision"] is None


def test_blocked_report_cannot_bypass_checks(tmp_path: Path) -> None:
    ledger, job, _, digest = ready(tmp_path, passed=False)
    with pytest.raises(PolicyError, match="blocked"):
        ledger.decide_report(job, digest, "accepted")


def test_rejection_requires_reason_and_preserves_it(tmp_path: Path) -> None:
    ledger, job, _, digest = ready(tmp_path)
    with pytest.raises(PolicyError, match="reason"):
        ledger.decide_report(job, digest, "rejected")
    ledger.decide_report(
        job, digest, "rejected", "Needs an independent technical comparison"
    )
    record = ledger.review_record(job)
    assert record["job"]["state"] == "rejected"
    assert record["decision"]["reason"] == "Needs an independent technical comparison"


def test_concurrent_owner_decisions_only_record_once(tmp_path: Path) -> None:
    ledger, job, _, digest = ready(tmp_path)

    def decide(_: int) -> bool:
        try:
            Ledger(ledger.path, 0).decide_report(job, digest, "accepted")
            return True
        except PolicyError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(decide, range(2))) == 1


def test_followups_keep_reviewer_gaps_missing_from_draft(tmp_path: Path) -> None:
    tasks = build_followups(
        ["Revenue history", "Revenue history"],
        [
            ("valuation", False, "Need diluted shares and dated prices"),
            ("identity", True, "Verified"),
        ],
        ["Correct the source attribution"],
    )
    assert len(tasks) == 3
    lines = save_followups(tmp_path, tasks, revised=True)
    assert "Need diluted shares" in "\n".join(lines)
    assert (
        json.loads((tmp_path / "followups.json").read_text())["review_applies_to"]
        == "pre_revision"
    )


def test_legacy_job_inspection_derives_gaps_without_acceptance(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Legacy", 3)
    ledger.start(job)
    ledger.complete_research(job, True)
    folder = tmp_path / job
    folder.mkdir()
    (folder / "analysis.json").write_text(
        json.dumps(
            {
                "text": json.dumps(
                    {"draft": {"missing_evidence": ["Financial statements"]}}
                )
            }
        )
    )
    (folder / "review.json").write_text(
        json.dumps(
            {
                "text": json.dumps(
                    {
                        "checks": [
                            {
                                "name": "valuation",
                                "passed": False,
                                "explanation": "Missing market prices",
                            }
                        ],
                        "corrections": [],
                    }
                )
            }
        )
    )
    result = inspect_job(ledger, tmp_path, job)
    assert len(result["followups"]["tasks"]) == 2
    assert not result["can_accept"]
    assert ledger.review_record(job)["decision"] is None


def test_invalid_saved_json_does_not_hide_diagnostics(tmp_path: Path) -> None:
    ledger, job, _, _ = ready(tmp_path, False)
    (tmp_path / job / "analysis.json").write_text(
        json.dumps({"text": "incomplete JSON"})
    )
    result = inspect_job(ledger, tmp_path, job)
    assert any("could not be parsed" in s for s in result["blockers"])


def test_path_traversal_rejected(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    with pytest.raises(PolicyError, match="actual job ID"):
        inspect_job(ledger, tmp_path, "../outside")
