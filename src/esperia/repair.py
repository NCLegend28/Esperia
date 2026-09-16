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


def plan_repair(ledger: Ledger, root: Path, parent_id: str) -> dict[str, Any]:
    """Assign saved gaps and validator failures without making model calls."""
    record = inspect_job(ledger, root, parent_id)
    if record["job"]["state"] not in {"blocked", "rejected"}:
        raise PolicyError("Only blocked or owner-rejected jobs can be repaired")
    if any(c["state"] != "settled" for c in record["calls"]):
        raise PolicyError("Reconcile uncertain parent calls before planning repairs")
    tasks = list(record["followups"]["tasks"])
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
    if not 1 <= len(assigned) <= 64 or sum(len(t["detail"]) for t in assigned) > 24000:
        raise PolicyError(
            "Repair needs 1–64 actionable tasks within the context budget"
        )
    folder = root / parent_id
    request = folder / "request.json"
    question = (
        json.loads(request.read_text())["question"]
        if request.exists()
        else record["job"]["title"]
    )
    if not isinstance(question, str) or not 1 <= len(question) <= 4000:
        raise PolicyError("Saved research question is invalid")
    return {
        "parent_id": parent_id,
        "question": question,
        "question_origin": "saved_request" if request.exists() else "legacy_job_title",
        "tasks": assigned,
    }


def repair_sources(root: Path, parent_id: str) -> list[str]:
    """Read original URL provenance for fresh collection; stale snapshots are not reused."""
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
    if not 1 <= len(urls) <= 12 or len(set(urls)) != len(urls):
        raise PolicyError("Repair needs 1–12 distinct approved source URLs")
    for url in urls:
        validate_url(url)
    return urls


def run_repair(
    ledger: Ledger,
    root: Path,
    parent_id: str,
    worker: Provider,
    reviewer: Provider | None,
    backend: str,
    urls: list[str],
    call_limit: int = 2,
    progress: Callable[[str], None] = print,
    use_discovery: bool = False,
) -> Path:
    """Execute assigned work in one analysis batch and one fresh review, with no recursive repair."""
    plan = plan_repair(ledger, root, parent_id)
    if not 1 <= len(urls) <= 12 or len(set(urls)) != len(urls):
        raise PolicyError("Repair needs 1–12 distinct approved source URLs")
    for url in urls:
        validate_url(url)
    key = sha256(
        json.dumps(
            [
                plan,
                urls,
                backend,
                getattr(worker, "cache_identity", ""),
                call_limit,
                use_discovery,
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    job = ledger.create_repair(parent_id, key, plan["tasks"], call_limit)
    output = root / job
    progress(f"Repair job: {job}; parent: {parent_id}")
    try:
        output.mkdir(parents=True, exist_ok=True)
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
            )
            if use_discovery
            else collect(urls, output / "evidence")
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
        )
    except Exception:
        ledger.fail_repair_tasks(job)
        raise
