"""Dispatch a bounded repair batch with durable lineage and independent review.

Example: plan_repair(ledger, research_root, parent_id)
Source collection uses explicit approved URLs; no open-web discovery or paid fallback.
"""

import json
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Any

from esperia.discovery import discover
from esperia.economy import run_economy
from esperia.evidence import collect, validate_url
from esperia.execution import Provider
from esperia.ledger import Ledger, PolicyError
from esperia.owner import inspect_job
from esperia.settings import Settings, save_settings


def plan_repair(ledger: Ledger, root: Path, parent_id: str) -> dict[str, Any]:
    """Assign saved gaps and validator failures without making model calls."""
    record = inspect_job(ledger, root, parent_id)
    if record["job"]["state"] not in {"blocked", "rejected"}:
        raise PolicyError("Only blocked or owner-rejected jobs can be repaired")
    if any(c["state"] != "settled" for c in record["calls"]):
        raise PolicyError("Reconcile uncertain parent calls before planning repairs")
    tasks = [
        task
        for task in record["followups"]["tasks"]
        if task["origin"] != "repair_reviewer" or record["repair"]["tasks"]
    ]
    if record["decision"] and record["decision"]["reason"]:
        tasks.append(
            {
                "origin": "owner",
                "criterion": "correction",
                "detail": record["decision"]["reason"],
            }
        )
    unique = {(t["criterion"], t["detail"]): t for t in tasks}
    assigned = [
        {
            "id": f"R{i}",
            "criterion": t["criterion"],
            "detail": t["detail"],
            "assignee": "researcher" if t["criterion"] != "correction" else "corrector",
            "reviewer": "independent_reviewer",
        }
        for i, t in enumerate(unique.values(), 1)
    ]
    if (
        not 1 <= len(assigned) <= ledger.settings.repair_tasks
        or sum(len(t["detail"]) for t in assigned) > ledger.settings.repair_chars
    ):
        raise PolicyError(
            f"Repair needs 1–{ledger.settings.repair_tasks} actionable tasks within the context budget"
        )
    folder = root / parent_id
    request = folder / "request.json"
    question = (
        json.loads(request.read_text())["question"]
        if request.exists()
        else record["job"]["title"]
    )
    if (
        not isinstance(question, str)
        or not 1 <= len(question) <= ledger.settings.question_chars
    ):
        raise PolicyError("Saved research question is invalid")
    return {
        "parent_id": parent_id,
        "question": question,
        "question_origin": "saved_request" if request.exists() else "legacy_job_title",
        "tasks": assigned,
    }


def repair_sources(
    root: Path, parent_id: str, settings: Settings | None = None
) -> list[str]:
    """Read original URL provenance for fresh collection; stale snapshots are not reused."""
    settings = settings or Settings()
    folder = root / parent_id
    provenance = folder / "source-provenance.json"
    sources = (
        json.loads(provenance.read_text())["sources"]
        if provenance.exists()
        else json.loads((folder / "evidence/sources.json").read_text())
    )
    discovery = folder / "evidence/discovery.json"
    if discovery.exists():
        urls = [str(url) for url in json.loads(discovery.read_text())["seeds"]]
    else:
        urls = [s["url"] for s in sources]
    if not 1 <= len(urls) <= settings.max_seeds or len(set(urls)) != len(urls):
        raise PolicyError(
            f"Repair needs 1–{settings.max_seeds} distinct public source URLs"
        )
    for url in urls:
        validate_url(url, settings)
    return urls


def run_repair(
    ledger: Ledger,
    root: Path,
    parent_id: str,
    worker: Provider,
    reviewer: Provider | None,
    backend: str,
    urls: list[str],
    call_limit: int | None = None,
    progress: Callable[[str], None] = print,
    use_discovery: bool = False,
    settings: Settings | None = None,
) -> Path:
    """Execute assigned work in one analysis batch and one fresh review, with no recursive repair."""
    settings = settings or ledger.settings
    call_limit = settings.repair_calls if call_limit is None else call_limit
    plan = plan_repair(ledger, root, parent_id)
    if not 1 <= len(urls) <= settings.max_seeds or len(set(urls)) != len(urls):
        raise PolicyError(
            f"Repair needs 1–{settings.max_seeds} distinct public source URLs"
        )
    for url in urls:
        validate_url(url, settings)
    key = sha256(
        json.dumps(
            [
                plan,
                urls,
                backend,
                getattr(worker, "cache_identity", ""),
                call_limit,
                use_discovery,
                settings.model_dump(mode="json"),
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    job = ledger.create_repair(parent_id, key, plan["tasks"], call_limit)
    output = root / job
    progress(f"Repair job: {job}; parent: {parent_id}")
    try:
        output.mkdir(parents=True, exist_ok=True)
        save_settings(settings, output)
        (output / "repair-plan.json").write_text(
            json.dumps(
                {
                    **plan,
                    "backend": backend,
                    "source_urls": urls,
                    "call_limit": call_limit,
                },
                indent=2,
            )
        )
        (output / "request.json").write_text(json.dumps({"question": plan["question"]}))
        sources = (
            discover(
                urls,
                plan["question"] + " " + " ".join(t["detail"] for t in plan["tasks"]),
                output / "evidence",
                settings=settings,
            )
            if use_discovery
            else collect(urls, output / "evidence", settings)
        )
        (output / "source-provenance.json").write_text(
            json.dumps(
                {
                    "archive": str(output / "evidence"),
                    "sources": [s.model_dump() for s in sources],
                },
                indent=2,
            )
        )
    except Exception:
        ledger.cancel(job)
        ledger.fail_repair_tasks(job)
        raise
    try:
        return run_economy(
            ledger,
            worker,
            job,
            plan["question"],
            sources,
            output,
            progress,
            reviewer=reviewer,
            refresh=True,
            repair_tasks=plan["tasks"],
            settings=settings,
        )
    except Exception:
        ledger.fail_repair_tasks(job)
        raise
