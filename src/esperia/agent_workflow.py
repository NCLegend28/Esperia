"""Owner-facing adaptive research execution and checkpoint controls.

Example: start_agent(ledger, settings, question, backend, mode, None, providers).
An investigation handoff feeds existing evidence-bound report/review gates.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from esperia.agent_loop import Journal, LoopError, LoopHalted
from esperia.economy import run_economy
from esperia.evidence import load_archive
from esperia.execution import Provider, StageRunner
from esperia.investigation import investigate
from esperia.ledger import Ledger
from esperia.research import SYSTEM, run_research
from esperia.search import check_search_configuration
from esperia.settings import Settings, save_settings
from esperia.timeframe import research_timeframe

ProviderFactory = Callable[[str, Settings], tuple[Any, Any]]


def report_reserve(settings: Settings, mode: str) -> int:
    """Reserve mandatory analysis and independent review before investigation."""
    return (
        2
        if mode == "economy"
        else min(
            settings.agent.read_calls,
            settings.documents,
            settings.requests,
            settings.max_seeds,
        )
        + 3
    )


def agent_directory(ledger: Ledger, settings: Settings, job_id: str) -> Path:
    """Resolve only an existing job UUID, never a caller-supplied path."""
    record = ledger.review_record(job_id)
    if record["job"]["id"] != job_id or Path(job_id).name != job_id:
        raise LoopError("Unknown agent job")
    return settings.research_root / job_id


def start_agent(
    ledger: Ledger,
    settings: Settings,
    question: str,
    backend: str,
    mode: str,
    max_calls: int | None,
    providers: ProviderFactory,
    progress: Callable[[str], None] = print,
) -> str:
    """Validate resources, reserve a job and execute the selected local/cloud worker."""
    settings = Settings.model_validate(
        {**settings.model_dump(), "backend": backend, "mode": mode}
    )
    if not question.strip() or len(question) > settings.question_chars:
        raise LoopError("Provide a question within the configured character budget")
    check_search_configuration(settings)
    reserve = report_reserve(settings, mode)
    required = settings.agent.steps + reserve
    limit = required if max_calls is None else max_calls
    if not required <= limit <= settings.max_calls:
        raise LoopError(
            f"Adaptive research needs {required}–{settings.max_calls} model calls: investigation decisions plus reserved report/review calls. Adjust agent.steps or the explicit cap."
        )
    worker, reviewer = providers(backend, settings)
    try:
        job_id = ledger.create_subscription(question[: settings.title_chars], limit)
        output = settings.research_root / job_id
        save_settings(settings, output)
        request = {
            "question": question,
            "timeframe": research_timeframe(question, datetime.now(UTC).date()),
            "backend": backend,
            "mode": mode,
            "call_limit": limit,
            "report_reserve": reserve,
        }
        (output / "request.json").write_text(json.dumps(request, indent=2))
        journal = Journal(output, settings.sqlite_timeout)
        journal.create(request)
        ledger.start(job_id)
        progress(f"Job: {job_id}")
        with journal.worker():
            execute_agent(ledger, settings, job_id, journal, worker, reviewer, progress)
        return job_id
    finally:
        worker.close()
        if reviewer:
            reviewer.close()


def resume_agent(
    ledger: Ledger,
    settings: Settings,
    job_id: str,
    providers: ProviderFactory,
    progress: Callable[[str], None] = print,
) -> None:
    """Resume an explicit known checkpoint using original settings and call budget."""
    output = agent_directory(ledger, settings, job_id)
    saved = Settings.model_validate_json((output / "resolved-config.json").read_text())
    journal = Journal(output, saved.sqlite_timeout)
    with journal.worker():
        state = journal.snapshot()
        if state["pending"] not in {None, "report"}:
            journal.mark("blocked", "uncertain_execution")
            ledger.block_research(job_id)
            raise LoopError(
                "An operation was interrupted; inspect model/tool calls. Resume never replays uncertain work"
            )
        record = ledger.review_record(job_id)
        if record["report"] is not None and state["pending"] == "report":
            report = record["report"]
            path = journal.output / "report.md"
            if (
                not path.is_file()
                or sha256(path.read_bytes()).hexdigest() != report["sha256"]
            ):
                raise LoopError("Registered report changed; inspect before continuing")
            journal.mark("completed", "registered_report_recovered", clear=True)
            progress(f"Report already registered: {path.resolve()}; no model calls")
            return
        if record["job"]["state"] != "running":
            raise LoopError("Only an unfinished running agent job can resume")
        if any(call["state"] != "settled" for call in ledger.list_calls(job_id)):
            raise LoopError("Unresolved model calls prevent resume")
        if state["status"] in {"blocked", "stopped", "completed"}:
            raise LoopError("Terminal agent work cannot be resumed")
        if state["pending"] == "report":
            journal.mark("ready", "resume_report_checkpoints", clear=True)
        journal.control("resume")
        request = state["request"]
        worker, reviewer = providers(request["backend"], saved)
        try:
            execute_agent(ledger, saved, job_id, journal, worker, reviewer, progress)
        finally:
            worker.close()
            if reviewer:
                reviewer.close()


def execute_agent(
    ledger: Ledger,
    settings: Settings,
    job_id: str,
    journal: Journal,
    worker: Provider,
    reviewer: Provider | None,
    progress: Callable[[str], None],
) -> None:
    """Investigate to a verified evidence handoff, then run fixed acceptance checks.

    Reporting restores only validated, matching completed stage checkpoints.
    Uncertain calls block resume. Pauses are honored before each model dispatch;
    calls already in flight may finish.
    """
    request = journal.snapshot()["request"]
    try:
        steps = journal.snapshot()["steps"]
        handed_off = bool(
            steps
            and steps[-1]["action"]["kind"] == "finish"
            and steps[-1]["observation"].get("accepted")
        )
        if not handed_off:
            runner = StageRunner(
                ledger,
                worker,
                job_id,
                journal.output,
                SYSTEM,
                progress,
                settings=settings,
            )
            investigate(runner, journal, settings)
        journal.begin("report")
        archive = journal.output / "evidence"
        if request.get("followup"):
            from esperia.followup_research import merge_evidence

            archive = merge_evidence(journal.output, settings)
        sources = load_archive(archive, settings)
        (journal.output / "source-provenance.json").write_text(
            json.dumps(
                {
                    "archive": str(archive),
                    "sources": [s.model_dump() for s in sources],
                },
                indent=2,
            )
        )
        report_function = run_economy if request["mode"] == "economy" else run_research
        repair_options = (
            {"repair_tasks": request["followup"]["tasks"]}
            if request.get("followup")
            else {}
        )
        report = report_function(
            ledger,
            worker,
            job_id,
            request["question"],
            sources,
            journal.output,
            progress=progress,
            reviewer=reviewer,
            settings=settings,
            started=True,
            before_call=journal.boundary,
            reuse_completed=True,
            **repair_options,
        )
        review_state = ledger.review_record(job_id)["job"]["state"]
        journal.mark(
            "completed",
            (
                "report_awaiting_owner"
                if review_state == "awaiting_owner"
                else "report_checks_failed"
            ),
            clear=True,
        )
        progress(f"Report: {report.resolve()}")
        progress(f"Inspect review and follow-ups: uv run esperia review {job_id}")
    except LoopHalted:
        state = journal.snapshot()
        if state["status"] != "paused" and state["control"] != "pause":
            ledger.block_research(job_id)
            if request.get("followup"):
                ledger.fail_repair_tasks(job_id)
        progress(
            f"Agent halted: {state['reason'] or state['control']}. Inspect with: uv run esperia agent {job_id}"
        )
    except BaseException:
        journal.mark("blocked", "execution_failed_or_interrupted")
        ledger.block_research(job_id)
        if request.get("followup"):
            ledger.fail_repair_tasks(job_id)
        raise
