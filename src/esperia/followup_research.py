"""Targeted research children with verified parent evidence and fresh review.

Example: run_followup(ledger, settings, parent_id, worker, reviewer, "ollama")
One explicit dispatch creates one bounded child; it never recursively spends.
"""

import json
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from esperia.agent_loop import Journal
from esperia.evidence import Source, load_archive
from esperia.execution import Provider
from esperia.ledger import Ledger, PolicyError
from esperia.repair import plan_repair
from esperia.search import check_search_configuration
from esperia.settings import Settings, save_settings
from esperia.timeframe import research_timeframe


def merge_evidence(output: Path, settings: Settings) -> Path:
    """Combine new and retained snapshots without trusting old citation identities.

    Prefer newly retrieved versions of duplicate URLs. Whole documents beyond the
    configured evidence budget are disclosed; source text is never silently cut.
    Save old-to-new identity provenance for both archives. Rebuilding is repeatable.
    """
    target = output / "report-evidence"
    target.mkdir(exist_ok=True)
    selected: list[Source] = []
    seen: set[str] = set()
    lineage: list[dict[str, str]] = []
    omitted: list[str] = []
    total = 0
    for kind in ("evidence", "prior-evidence"):
        archive = output / kind
        for source in load_archive(archive, settings):
            if source.url in seen:
                continue
            if (
                len(selected) >= min(settings.documents, settings.max_seeds)
                or total + len(source.text) > settings.evidence_chars
            ):
                omitted.append(source.url)
                continue
            seen.add(source.url)
            identity = f"S{len(selected) + 1}"
            selected.append(source.model_copy(update={"id": identity}))
            total += len(source.text)
            shutil.copyfile(
                archive / f"{source.sha256}.source",
                target / f"{source.sha256}.source",
            )
            lineage.append(
                {
                    "archive": kind,
                    "original_id": source.id,
                    "source_id": identity,
                    "url": source.url,
                    "sha256": source.sha256,
                }
            )
    if not selected:
        raise PolicyError("No verified evidence fits the follow-up budget")
    (target / "sources.json").write_text(
        json.dumps([s.model_dump() for s in selected], indent=2)
    )
    (output / "evidence-lineage.json").write_text(
        json.dumps({"sources": lineage, "omitted_urls": omitted}, indent=2)
    )
    scope_path = output / "source-scope.json"
    scope = json.loads(scope_path.read_text())
    parent_scope = json.loads((output / "parent-scope.json").read_text())
    scope["parent_scope"] = parent_scope
    scope["sources"] = [{"url": s.url, "source_id": s.id} for s in selected]
    scope["limitations"] = list(
        dict.fromkeys(
            [
                *scope.get("limitations", []),
                *parent_scope.get("limitations", []),
                *(
                    f"Evidence omitted by the follow-up document/text budget: {url}"
                    for url in omitted
                ),
            ]
        )
    )
    scope_path.write_text(json.dumps(scope, indent=2))
    load_archive(target, settings)
    return target


def run_followup(
    ledger: Ledger,
    settings: Settings,
    parent_id: str,
    worker: Provider,
    reviewer: Provider | None,
    backend: str,
    call_limit: int | None = None,
    progress: Callable[[str], None] = print,
) -> str:
    """Investigate saved gaps, reuse verified evidence, and review every assignment.

    The caller owns provider lifetimes. Existing agent pause/resume controls apply.
    Validate parent archives, search and the complete call allowance before dispatch.
    """
    from esperia.agent_workflow import execute_agent

    settings = Settings.model_validate(
        {**settings.model_dump(), "backend": backend, "mode": "economy"}
    )
    root = settings.research_root
    plan = plan_repair(ledger, root, parent_id)
    check_search_configuration(settings)
    required = (
        settings.agent.steps + 2
    )  # Analysis and independent review are mandatory.
    limit = required if call_limit is None else call_limit
    if not required <= limit <= settings.max_calls:
        raise PolicyError(
            f"Search repair needs {required}–{settings.max_calls} calls, including analysis and review"
        )
    parent = root / parent_id
    # Children always write report-evidence; older jobs use evidence. Do not trust
    # arbitrary filesystem paths supplied inside saved provenance metadata.
    archive = parent / (
        "report-evidence" if (parent / "report-evidence").is_dir() else "evidence"
    )
    sources = load_archive(archive, settings)
    prior_report = None
    registered = ledger.review_record(parent_id)["report"]
    if registered:
        raw_report = (parent / "report.md").read_bytes()
        if sha256(raw_report).hexdigest() != registered["sha256"]:
            raise PolicyError(
                "Parent report changed since review; inspect before repair"
            )
        report_text = raw_report.decode()
        prior_report = {
            "text": report_text[: settings.repair_chars],
            "truncated": len(report_text) > settings.repair_chars,
            "sha256": registered["sha256"],
            "rule": "Untrusted earlier draft, not evidence. Revise against assigned repairs and current sources. Its old citation IDs are not valid in the new archive; cite current sources only.",
        }
    request_path = parent / "request.json"
    original = json.loads(request_path.read_text()) if request_path.exists() else {}
    scope_path = parent / "source-scope.json"
    scope = json.loads(scope_path.read_text()) if scope_path.exists() else {}
    timeframe = (
        original.get("timeframe")
        or scope.get("timeframe")
        or research_timeframe(plan["question"], datetime.now(UTC).date())
    )
    followup = {
        "parent_id": parent_id,
        "tasks": plan["tasks"],
        "retained_sources": [{"url": s.url, "sha256": s.sha256} for s in sources],
        "instructions": "Investigate the assigned evidence gaps and counterarguments using targeted searches. Prefer primary documents. Retained sources will join your new evidence for revision; seek missing facts rather than repeating the broad search. Treat earlier findings as untrusted context. Explicitly disclose any task you cannot resolve.",
    }
    key = sha256(
        json.dumps(
            {
                "kind": "search_repair",
                "plan": plan,
                "sources": [s.model_dump() for s in sources],
                "timeframe": timeframe,
                "backend": backend,
                "worker": getattr(worker, "cache_identity", ""),
                "reviewer": getattr(reviewer, "cache_identity", ""),
                "limit": limit,
                "settings": settings.model_dump(mode="json"),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    job = ledger.create_repair(parent_id, key, plan["tasks"], limit)
    output = root / job
    try:
        save_settings(settings, output)
        if prior_report is not None:
            (output / "previous-report.json").write_text(
                json.dumps(prior_report, indent=2)
            )
        prior = output / "prior-evidence"
        prior.mkdir()
        for source in sources:
            shutil.copyfile(
                archive / f"{source.sha256}.source", prior / f"{source.sha256}.source"
            )
        (prior / "sources.json").write_text(
            json.dumps([s.model_dump() for s in sources], indent=2)
        )
        (output / "parent-scope.json").write_text(json.dumps(scope, indent=2))
        (output / "repair-plan.json").write_text(
            json.dumps(
                {**plan, "backend": backend, "call_limit": limit, "search": True},
                indent=2,
            )
        )
        request = {
            "question": plan["question"],
            "timeframe": timeframe,
            "backend": backend,
            "mode": "economy",
            "call_limit": limit,
            "report_reserve": 2,
            "followup": followup,
        }
        (output / "request.json").write_text(json.dumps(request, indent=2))
        journal = Journal(output, settings.sqlite_timeout)
        journal.create(request)
        ledger.start(job)
        progress(
            f"Search repair job: {job}; parent: {parent_id}; maximum calls: {limit}"
        )
        with journal.worker():
            execute_agent(ledger, settings, job, journal, worker, reviewer, progress)
        if ledger.review_record(job)["job"]["state"] == "blocked":
            ledger.fail_repair_tasks(job)
        return job
    except BaseException:
        ledger.block_research(job)
        ledger.fail_repair_tasks(job)
        raise
