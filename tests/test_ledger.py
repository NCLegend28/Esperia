"""Verify financial accounting and approval boundaries across connections."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from esperia.ledger import Ledger, PolicyError


def test_concurrent_reservations_cannot_overspend(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite"
    Ledger(path, 100, 100)

    def reserve(_: int) -> bool:
        try:
            Ledger(path, 100, 100).create("Report", 60)
            return True
        except PolicyError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(4))) == 1


def test_approval_and_claim_are_enforced_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite"
    ledger = Ledger(path, 500)
    job = ledger.create("Review proposal", 100, requires_approval=True)
    ledger = Ledger(path, 500)
    with pytest.raises(PolicyError):
        ledger.start(job)
    ledger.approve(job)
    ledger.start(job)
    with pytest.raises(PolicyError):
        ledger.start(job)
    with pytest.raises(PolicyError):
        ledger.approve(job)


def test_settlement_releases_only_unused_budget(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 100, 100)
    job = ledger.create("Report", 100)
    ledger.start(job)
    ledger.finish(job, 40)
    assert ledger.list_jobs()[0]["state"] == "awaiting_review"
    with pytest.raises(PolicyError):
        ledger.finish(job, 0)
    ledger.create("Next", 60)
    with pytest.raises(PolicyError):
        ledger.create("Over budget", 1)


def test_unexpected_provider_overage_is_recorded(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 100, 100)
    job = ledger.create("Report", 100)
    ledger.start(job)
    ledger.finish(job, 120)
    assert ledger.list_jobs()[0]["actual"] == 120
    with pytest.raises(PolicyError):
        ledger.create("Next", 1)


def test_cancel_releases_reservation(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 100, 100)
    job = ledger.create("Proposal", 100, True)
    ledger.cancel(job)
    ledger.create("Replacement", 100)
    with pytest.raises(PolicyError):
        ledger.approve(job)


@pytest.mark.parametrize("amount", [-1, 0, 501])
def test_per_job_limit(tmp_path: Path, amount: int) -> None:
    with pytest.raises(PolicyError):
        Ledger(tmp_path / "jobs.sqlite", 6500).create("Report", amount)
