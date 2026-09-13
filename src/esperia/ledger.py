"""Durable jobs and atomic spending reservations.

Example: Ledger(Path("jobs.sqlite"), 6500).create("Quantum research", 500)
Amounts are integer US cents. This module performs no external actions.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class PolicyError(ValueError):
    """A requested transition would violate a budget or approval rule."""


class Ledger:
    """Store jobs in an explicitly supplied SQLite database and budget scope."""

    def __init__(self, path: Path, monthly_limit_cents: int, max_job_cents: int = 500):
        if monthly_limit_cents < 0 or max_job_cents <= 0:
            raise ValueError("Invalid spending limits")
        self.path = path
        self.limit = monthly_limit_cents
        self.max_job = max_job_cents
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, period TEXT NOT NULL,
                state TEXT NOT NULL, reserved INTEGER NOT NULL CHECK(reserved >= 0),
                actual INTEGER NOT NULL DEFAULT 0 CHECK(actual >= 0),
                requires_approval INTEGER NOT NULL CHECK(requires_approval IN (0,1))
            )""")

    def create_subscription(self, title: str, call_limit: int = 16) -> str:
        """Create a quota-limited job without reserving any API dollars."""
        if not title.strip() or len(title) > 240 or not 1 <= call_limit <= 32:
            raise ValueError("Invalid subscription job title or call limit")
        with self._transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS subscription_jobs (job_id TEXT PRIMARY KEY, call_limit INTEGER NOT NULL)"
            )
            job_id = str(uuid4())
            connection.execute(
                "INSERT INTO jobs (id,title,period,state,reserved,requires_approval) VALUES (?,?,?,'queued',0,0)",
                (job_id, title, datetime.now(UTC).strftime("%Y-%m")),
            )
            connection.execute(
                "INSERT INTO subscription_jobs VALUES (?,?)", (job_id, call_limit)
            )
        return job_id

    def reserve_subscription_call(self, job_id: str, stage: str, model: str) -> str:
        """Enforce a durable per-job call cap with zero monetary reservation."""
        with self._transaction() as connection:
            self._ensure_calls(connection)
            job = connection.execute(
                "SELECT j.state,s.call_limit FROM jobs j JOIN subscription_jobs s ON j.id=s.job_id WHERE j.id=?",
                (job_id,),
            ).fetchone()
            if job is None or job["state"] != "running":
                raise PolicyError("Only running subscription jobs can dispatch")
            count = connection.execute(
                "SELECT COUNT(*) FROM calls WHERE job_id=?", (job_id,)
            ).fetchone()[0]
            if count >= job["call_limit"]:
                raise PolicyError("Subscription job call limit reached")
            call_id = str(uuid4())
            try:
                connection.execute(
                    "INSERT INTO calls (id,job_id,stage,model,reserved,state) VALUES (?,?,?,?,0,'pending')",
                    (call_id, job_id, stage, model),
                )
            except sqlite3.IntegrityError:
                raise PolicyError(
                    "Stage already dispatched; no automatic replay"
                ) from None
            return call_id

    def _ensure_calls(self, connection: sqlite3.Connection) -> None:
        """Create the per-call usage ledger for existing local databases."""
        connection.execute("""CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL, stage TEXT NOT NULL,
            model TEXT NOT NULL, reserved INTEGER NOT NULL, actual INTEGER,
            state TEXT NOT NULL, response_id TEXT, UNIQUE(job_id,stage)
        )""")

    def reserve_call(self, job_id: str, stage: str, model: str, cents: int) -> str:
        """Reserve within a running job before dispatch, refusing cross-month replay."""
        if cents <= 0:
            raise ValueError("Call reservation must be positive")
        with self._transaction() as connection:
            self._ensure_calls(connection)
            job = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if job is None or job["state"] != "running":
                raise PolicyError("Only running jobs may reserve calls")
            if job["period"] != datetime.now(UTC).strftime("%Y-%m"):
                raise PolicyError(
                    "Cross-month work requires owner reconciliation before continuing"
                )
            held = connection.execute(
                "SELECT COALESCE(SUM(reserved),0) FROM calls WHERE job_id = ? AND state != 'settled'",
                (job_id,),
            ).fetchone()[0]
            if held + cents > job["reserved"]:
                raise PolicyError("Insufficient remaining per-job budget")
            call_id = str(uuid4())
            try:
                connection.execute(
                    "INSERT INTO calls (id,job_id,stage,model,reserved,state) VALUES (?,?,?,?,?,'pending')",
                    (call_id, job_id, stage, model, cents),
                )
            except sqlite3.IntegrityError:
                raise PolicyError(
                    "This stage was already dispatched; inspect its result before retrying"
                ) from None
            return call_id

    def uncertain_call(self, call_id: str) -> None:
        """Keep the full liability reserved when provider outcome is unknown."""
        with self._transaction() as connection:
            connection.execute(
                "UPDATE calls SET state = 'uncertain' WHERE id = ? AND state = 'pending'",
                (call_id,),
            )

    def settle_call(self, call_id: str, cents: int, response_id: str) -> None:
        """Record conservatively priced observed tokens exactly once."""
        if cents < 0:
            raise ValueError("Negative cost is invalid")
        with self._transaction() as connection:
            call = connection.execute(
                "SELECT * FROM calls WHERE id = ? AND state = 'pending'", (call_id,)
            ).fetchone()
            if call is None:
                raise PolicyError("Call is missing or already settled")
            connection.execute(
                "UPDATE calls SET state = 'settled', actual = ?, response_id = ? WHERE id = ?",
                (cents, response_id, call_id),
            )
            connection.execute(
                "UPDATE jobs SET actual = actual + ?, reserved = MAX(0,reserved - ?) WHERE id = ?",
                (cents, cents, call["job_id"]),
            )

    def complete_research(self, job_id: str, passed: bool) -> None:
        """Release unused funds while keeping reviewer approval distinct from owner acceptance."""
        with self._transaction() as connection:
            self._ensure_calls(connection)
            pending = connection.execute(
                "SELECT COUNT(*) FROM calls WHERE job_id = ? AND state != 'settled'",
                (job_id,),
            ).fetchone()[0]
            if pending:
                raise PolicyError("Uncertain calls must be reconciled first")
            changed = connection.execute(
                "UPDATE jobs SET state = ?, reserved = 0 WHERE id = ? AND state = 'running'",
                ("awaiting_owner" if passed else "blocked", job_id),
            ).rowcount
            if changed != 1:
                raise PolicyError("Research job is not running")

    def block_research(self, job_id: str) -> None:
        """Release unused funds but preserve every uncertain call reservation."""
        with self._transaction() as connection:
            self._ensure_calls(connection)
            held = connection.execute(
                "SELECT COALESCE(SUM(reserved),0) FROM calls WHERE job_id = ? AND state != 'settled'",
                (job_id,),
            ).fetchone()[0]
            connection.execute(
                "UPDATE jobs SET state = 'blocked', reserved = ? WHERE id = ? AND state = 'running'",
                (held, job_id),
            )

    def list_calls(self, job_id: str) -> list[dict[str, Any]]:
        """Inspect agent stages, models, usage and unresolved provider calls."""
        with self._transaction() as connection:
            self._ensure_calls(connection)
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM calls WHERE job_id = ? ORDER BY rowid", (job_id,)
                )
            ]

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create(
        self, title: str, reserve_cents: int, requires_approval: bool = False
    ) -> str:
        """Reserve a job budget atomically; concurrent jobs share the same cap."""
        title = title.strip()
        if not title or len(title) > 240:
            raise ValueError("Title must contain 1–240 characters")
        if not 0 < reserve_cents <= self.max_job:
            raise PolicyError(
                "Reservation exceeds the per-job limit or is not positive"
            )
        period = datetime.now(UTC).strftime("%Y-%m")
        job_id = str(uuid4())
        with self._transaction() as connection:
            allocated = connection.execute(
                "SELECT COALESCE(SUM(reserved + CASE WHEN period = ? THEN actual ELSE 0 END), 0) FROM jobs",
                (period,),
            ).fetchone()[0]
            if allocated + reserve_cents > self.limit:
                raise PolicyError(
                    "Monthly budget exhausted; existing jobs retain their reservations"
                )
            connection.execute(
                "INSERT INTO jobs (id,title,period,state,reserved,requires_approval) VALUES (?,?,?,?,?,?)",
                (
                    job_id,
                    title,
                    period,
                    "awaiting_approval" if requires_approval else "queued",
                    reserve_cents,
                    int(requires_approval),
                ),
            )
        return job_id

    def list_jobs(self) -> list[dict[str, Any]]:
        """Return persisted jobs without making model calls."""
        with self._transaction() as connection:
            return [
                dict(row)
                for row in connection.execute("SELECT * FROM jobs ORDER BY rowid")
            ]

    def approve(self, job_id: str) -> None:
        """Release an approval hold, locally as the trusted workspace owner."""
        self._transition(job_id, "awaiting_approval", "queued")

    def start(self, job_id: str) -> None:
        """Claim a queued job exactly once; approval holds cannot be bypassed."""
        self._transition(job_id, "queued", "running")

    def _transition(self, job_id: str, previous: str, target: str) -> None:
        with self._transaction() as connection:
            changed = connection.execute(
                "UPDATE jobs SET state = ? WHERE id = ? AND state = ?",
                (target, job_id, previous),
            ).rowcount
            if changed != 1:
                raise PolicyError(f"Job must exist and be {previous}")

    def finish(self, job_id: str, actual_cents: int) -> None:
        """Record final observed cost even if a provider exceeded its estimate.

        This is execution completion, not reviewer or user acceptance. The cost
        remains visible and reduces capacity for future reservations.
        """
        if actual_cents < 0:
            raise ValueError("Actual cost cannot be negative")
        with self._transaction() as connection:
            self._ensure_calls(connection)
            if connection.execute(
                "SELECT COUNT(*) FROM calls WHERE job_id = ?", (job_id,)
            ).fetchone()[0]:
                raise PolicyError(
                    "Metered jobs must use complete_research, not legacy settlement"
                )
            changed = connection.execute(
                "UPDATE jobs SET state = 'awaiting_review', actual = ?, reserved = 0 WHERE id = ? AND state = 'running'",
                (actual_cents, job_id),
            ).rowcount
            if changed != 1:
                raise PolicyError(
                    "Only running jobs can finish; repeated settlement is rejected"
                )

    def cancel(self, job_id: str) -> None:
        """Cancel unstarted work and release its unused reservation."""
        with self._transaction() as connection:
            changed = connection.execute(
                "UPDATE jobs SET state = 'cancelled', reserved = 0 WHERE id = ? AND state IN ('queued','awaiting_approval')",
                (job_id,),
            ).rowcount
            if changed != 1:
                raise PolicyError("Only unstarted jobs can be cancelled")
