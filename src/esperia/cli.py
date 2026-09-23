"""Local owner console. Example: uv run esperia doctor.

Research uses the saved Codex ChatGPT subscription login, never API credits.
This trusted owner console must never be exposed as an agent tool or network service.
"""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from pydantic import ValidationError

from esperia.agent_loop import Journal, LoopError
from esperia.agent_workflow import agent_directory, resume_agent, start_agent
from esperia.discovery import DiscoveryFailure, discover
from esperia.economy import run_economy
from esperia.evidence import collect, load_archive
from esperia.execution import OutputValidationError, StageRunner
from esperia.followup_research import run_followup
from esperia.ledger import Ledger, PolicyError
from esperia.llama import LlamaProvider
from esperia.notebook import NotebookError
from esperia.notebook_cli import add_library_commands, run_library
from esperia.ollama import OllamaProvider
from esperia.owner import inspect_job
from esperia.provider import ProviderFailure
from esperia.question_assistant import frame_question
from esperia.repair import plan_repair, repair_sources, run_repair
from esperia.research import SYSTEM, run_research
from esperia.search import check_search_configuration, search_runtime
from esperia.settings import Profile, Settings, load_settings, save_settings
from esperia.sourcing import resolve_sources, resolve_tool_sources
from esperia.subscription import CodexSubscriptionProvider, ConfigurationError
from esperia.tools import ToolError


def load_manifest(path: Path) -> list[str]:
    """Read an explicit owner-controlled source manifest; URLs are validated by collector."""
    value = json.loads(path.read_text())
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigurationError(
            "Source manifest must be a JSON array of URLs; check your --sources file"
        )
    return value


def integer_setting(name: str, default: int, minimum: int) -> int:
    """Validate integer configuration without echoing user-supplied values."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ConfigurationError(
            f"{name} must be a whole number in .env.dev or your environment."
        ) from None
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}.")
    return value


def research_providers(
    backend: str,
    settings: Settings | None = None,
) -> tuple[
    CodexSubscriptionProvider | LlamaProvider | OllamaProvider,
    CodexSubscriptionProvider | None,
]:
    """Select only explicitly requested local/subscription backends; never fall back."""
    settings = settings or Settings()
    if backend == "codex":
        worker: CodexSubscriptionProvider | LlamaProvider | OllamaProvider = (
            CodexSubscriptionProvider(settings)
        )
    elif backend in {"ollama", "ollama-hybrid"}:
        worker = OllamaProvider(settings=settings)
    else:
        worker = LlamaProvider(settings=settings)
    try:
        worker.check_login()
        reviewer = (
            CodexSubscriptionProvider(settings)
            if backend in {"hybrid", "ollama-hybrid"}
            else None
        )
        if reviewer:
            reviewer.check_login()
        return worker, reviewer
    except Exception:
        worker.close()
        raise


def main() -> None:
    """Dispatch owner commands with environment isolation and redacted errors."""
    parser = argparse.ArgumentParser(description="Esperia research console")
    parser.add_argument(
        "--env", choices=["dev", "staging", "production"], default="dev"
    )
    parser.add_argument(
        "--workspace", type=Path, help="Workspace for environment and relative paths"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Validated JSON settings; otherwise ESPERIA_CONFIG or workspace esperia.json",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    add_library_commands(commands)
    question = commands.add_parser(
        "question", help="Develop a research question with the research guide"
    )
    question.add_argument("message")
    question.add_argument("--continue", dest="note_id")
    question.add_argument("--collection", action="append", default=[])
    question.add_argument("--backend", choices=["codex", "ollama", "llama"])
    commands.add_parser("config", help="Print resolved public configuration")
    commands.add_parser("jobs", help="List persistent jobs")
    doctor = commands.add_parser(
        "doctor", help="Check configuration without generation"
    )
    doctor.add_argument(
        "--backend",
        choices=["codex", "llama", "hybrid", "ollama", "ollama-hybrid"],
        default=None,
    )
    calls = commands.add_parser("calls", help="Inspect stages/models/costs for a job")
    calls.add_argument("job_id")
    create = commands.add_parser("create", help="Reserve a job; does not execute it")
    create.add_argument("title")
    create.add_argument("--budget-cents", type=int, required=True)
    create.add_argument("--approval", action="store_true")
    for action in ["approve", "cancel"]:
        command = commands.add_parser(action)
        command.add_argument("job_id")
    review_command = commands.add_parser(
        "review",
        help="Inspect report, consolidated follow-ups and acceptance eligibility; no model calls",
    )
    review_command.add_argument("job_id")
    for action in ["accept", "reject"]:
        decision = commands.add_parser(
            action, help="Record an owner decision on a specific reviewed report"
        )
        decision.add_argument("job_id")
        decision.add_argument("--report-sha256", required=True)
        decision.add_argument("--reason", required=action == "reject", default="")
    repair_command = commands.add_parser(
        "repair", help="Assign saved blockers to a bounded child research job"
    )
    repair_command.add_argument("job_id")
    repair_command.add_argument(
        "--profile", type=Path, help="Override the parent research profile"
    )
    repair_command.add_argument("--no-discovery", action="store_true")
    repair_command.add_argument(
        "--search",
        action="store_true",
        help="Investigate saved gaps using configured search and verified parent evidence",
    )
    repair_command.add_argument(
        "--plan",
        action="store_true",
        help="Preview assignments without collection or generation",
    )
    repair_command.add_argument(
        "--backend",
        choices=["codex", "llama", "hybrid", "ollama", "ollama-hybrid"],
        default=None,
    )
    repair_command.add_argument(
        "--sources",
        type=Path,
        help="Approved supplemental/replacement URL manifest; otherwise refetch original URLs",
    )
    repair_command.add_argument("--max-calls", type=int)
    discover_command = commands.add_parser(
        "discover", help="Collect linked filings and PDFs without model calls"
    )
    discover_command.add_argument("question")
    discover_command.add_argument("--sources", type=Path, required=True)
    gather = commands.add_parser(
        "collect", help="Archive approved public sources without model calls"
    )
    gather.add_argument("--sources", type=Path, required=True)
    research = commands.add_parser(
        "research", help="Collect sources and run subscription-backed analysis/review"
    )
    research.add_argument("question")
    research.add_argument(
        "--profile", type=Path, help="Versioned research profile JSON"
    )
    research.add_argument(
        "--no-discovery",
        action="store_true",
        help="Read only the explicit source manifest",
    )
    research.add_argument("--sources", type=Path)
    research.add_argument(
        "--archive",
        type=Path,
        help="Reuse a verified recent source archive instead of downloading",
    )
    research.add_argument("--max-calls", type=int)
    research.add_argument("--mode", choices=["economy", "deep"], default=None)
    research.add_argument(
        "--backend",
        choices=["codex", "llama", "hybrid", "ollama", "ollama-hybrid"],
        default=None,
    )
    research.add_argument(
        "--refresh", action="store_true", help="Bypass validated stage cache"
    )
    investigate_command = commands.add_parser(
        "investigate",
        help="Adaptively search/read/replan, then run evidence-bound analysis and review",
    )
    investigate_command.add_argument("question")
    investigate_command.add_argument(
        "--profile", type=Path, help="Versioned research profile JSON"
    )
    investigate_command.add_argument(
        "--backend",
        choices=["codex", "llama", "hybrid", "ollama", "ollama-hybrid"],
        default=None,
    )
    investigate_command.add_argument(
        "--mode", choices=["economy", "deep"], default=None
    )
    investigate_command.add_argument("--max-calls", type=int)
    agent_command = commands.add_parser(
        "agent", help="Inspect or control an adaptive research job"
    )
    agent_command.add_argument("job_id")
    agent_command.add_argument(
        "--action", choices=["status", "pause", "stop", "resume"], default="status"
    )
    args = parser.parse_args()
    try:
        config_path = args.config or (
            Path(os.environ["ESPERIA_CONFIG"]) if os.getenv("ESPERIA_CONFIG") else None
        )
        workspace = (
            args.workspace
            or (config_path.resolve().parent if config_path else Path.cwd())
        ).resolve()
        if config_path is not None and not config_path.is_absolute():
            config_path = workspace / config_path
        load_dotenv(workspace / f".env.{args.env}", override=False)
        if os.getenv("APP_ENV", args.env) != args.env:
            raise ConfigurationError("APP_ENV does not match selected environment")
        if args.env != "dev":
            raise ConfigurationError("Cloud environments are not enabled yet")
        if config_path is None and (workspace / "esperia.json").is_file():
            config_path = workspace / "esperia.json"
        settings = load_settings(config_path, workspace)
        overrides: dict[str, object] = {}
        legacy = {
            "ESPERIA_DATABASE": "database",
            "ESPERIA_DATA_ROOT": "data_root",
            "ESPERIA_MONTHLY_CENTS": "monthly_cents",
            "ESPERIA_JOB_CENTS": "job_cents",
            "ESPERIA_OLLAMA_URL": "ollama_url",
            "ESPERIA_OLLAMA_MODEL": "ollama_model",
            "ESPERIA_OLLAMA_CONTEXT": "ollama_context",
            "ESPERIA_OLLAMA_TIMEOUT_SECONDS": "ollama_timeout",
            "ESPERIA_LLAMA_URL": "llama_url",
            "ESPERIA_LLAMA_MODEL": "llama_model",
        }
        for env, field in legacy.items():
            if env in os.environ:
                overrides[field] = os.environ[env]
        if getattr(args, "profile", None):
            overrides["profile"] = Profile.model_validate_json(
                (workspace / args.profile).read_text()
            ).model_dump()
        settings = Settings.model_validate({**settings.model_dump(), **overrides})
        settings = settings.model_copy(
            update={
                "data_root": (workspace / settings.data_root).resolve(),
                "database": (
                    (workspace / settings.database).resolve()
                    if settings.database
                    else None
                ),
            }
        )
        if hasattr(args, "backend"):
            args.backend = args.backend or (
                settings.repair_backend
                if args.command == "repair"
                else settings.backend
            )
        if hasattr(args, "mode"):
            args.mode = args.mode or settings.mode
        if args.command in {"research", "investigate"}:
            settings = settings.model_copy(
                update={"backend": args.backend, "mode": args.mode}
            )
        if args.command == "question":
            if args.backend not in {"codex", "ollama", "llama"}:
                raise ConfigurationError(
                    "Question preparation requires a standalone --backend: codex, ollama or llama"
                )
            settings = settings.model_copy(update={"backend": args.backend})
        if getattr(args, "sources", None):
            args.sources = workspace / args.sources
        if getattr(args, "archive", None):
            args.archive = workspace / args.archive
        if args.command == "config":
            print(settings.model_dump_json(indent=2))
            return
        if args.command == "library":
            run_library(args, settings, workspace)
            return
        ledger = Ledger(
            settings.database or settings.data_root / "jobs.sqlite",
            settings.monthly_cents,
            settings.job_cents,
            settings,
        )
        if args.command == "question":
            provider, reviewer = research_providers(args.backend, settings)
            try:
                result = frame_question(
                    ledger,
                    settings,
                    provider,
                    args.message,
                    note_id=args.note_id,
                    collections=args.collection,
                )
                print(json.dumps(result, indent=2))
            finally:
                provider.close()
                if reviewer:
                    reviewer.close()
        elif args.command == "doctor":
            provider, reviewer = research_providers(args.backend, settings)
            print(
                json.dumps(
                    {
                        "execution": args.backend,
                        "api_fallback": False,
                        "codex_executable": getattr(provider, "binary", None),
                        "ready": True,
                        "default_max_calls": settings.call_budget(settings.mode),
                        "models": (
                            [provider.model_name]
                            if isinstance(provider, (LlamaProvider, OllamaProvider))
                            else [
                                settings.planner_model,
                                settings.analyst_model,
                                settings.reviewer_model,
                                settings.source_model,
                            ]
                        ),
                        "generation_checked": False,
                        "local_response_timeout_seconds": getattr(
                            provider, "timeout_seconds", None
                        ),
                        "cloud_deployed": False,
                    },
                    indent=2,
                )
            )
            provider.close()
            if reviewer:
                reviewer.close()
        elif args.command == "create":
            print(ledger.create(args.title, args.budget_cents, args.approval))
        elif args.command == "jobs":
            print(json.dumps(ledger.list_jobs(), indent=2))
        elif args.command == "calls":
            print(json.dumps(ledger.list_calls(args.job_id), indent=2))
        elif args.command == "approve":
            ledger.approve(args.job_id)
        elif args.command == "cancel":
            ledger.cancel(args.job_id)
        elif args.command == "review":
            print(
                json.dumps(
                    inspect_job(ledger, settings.research_root, args.job_id),
                    indent=2,
                )
            )
        elif args.command in {"accept", "reject"}:
            ledger.decide_report(
                args.job_id,
                args.report_sha256,
                "accepted" if args.command == "accept" else "rejected",
                args.reason,
            )
            print(
                f"Owner decision recorded: {args.command}; no external action was authorized."
            )
        elif args.command == "repair":
            root = settings.research_root
            parent_config = root / args.job_id / "resolved-config.json"
            # Validate the job identifier before reading anything under its folder.
            inspect_job(ledger, root, args.job_id)
            if not args.profile and config_path is None and parent_config.is_file():
                parent_settings = Settings.model_validate_json(
                    parent_config.read_text()
                )
                settings = settings.model_copy(
                    update={"profile": parent_settings.profile}
                )
            if args.search and (args.sources or args.no_discovery):
                raise ValueError(
                    "--search cannot be combined with --sources or --no-discovery"
                )
            plan = plan_repair(ledger, root, args.job_id)
            if args.plan:
                print(json.dumps(plan, indent=2))
            else:
                urls = (
                    load_manifest(args.sources)
                    if args.sources
                    else (
                        []
                        if args.search
                        else repair_sources(root, args.job_id, settings)
                    )
                )
                provider, reviewer = research_providers(args.backend, settings)
                try:
                    if args.search:
                        run_followup(
                            ledger,
                            settings,
                            args.job_id,
                            provider,
                            reviewer,
                            args.backend,
                            args.max_calls,
                            lambda message: print(message, flush=True),
                        )
                        return
                    report = run_repair(
                        ledger,
                        root,
                        args.job_id,
                        provider,
                        reviewer,
                        args.backend,
                        urls,
                        args.max_calls,
                        lambda message: print(message, flush=True),
                        use_discovery=not args.no_discovery,
                        settings=settings,
                    )
                    print(f"Report: {report.resolve()}")
                    print(f"Inspect repair: uv run esperia review {report.parent.name}")
                finally:
                    provider.close()
                    if reviewer:
                        reviewer.close()
        elif args.command == "discover":
            target = settings.data_root / "evidence" / str(uuid4())
            print(f"Discovery archive: {target.resolve()}", flush=True)
            sources = discover(
                load_manifest(args.sources), args.question, target, settings=settings
            )
            print(f"Archived {len(sources)} discovered sources: {target.resolve()}")
        elif args.command == "collect":
            target = settings.data_root / "evidence" / str(uuid4())
            sources = collect(load_manifest(args.sources), target, settings)
            print(f"Archived {len(sources)} sources: {target.resolve()}")
        elif args.command == "investigate":
            start_agent(
                ledger,
                settings,
                args.question,
                args.backend,
                args.mode,
                args.max_calls,
                research_providers,
                lambda message: print(message, flush=True),
            )
        elif args.command == "agent":
            directory = agent_directory(ledger, settings, args.job_id)
            journal = Journal(directory, settings.sqlite_timeout)
            if args.action == "status":
                print(json.dumps(journal.snapshot(), indent=2))
            elif args.action == "resume":
                resume_agent(
                    ledger,
                    settings,
                    args.job_id,
                    research_providers,
                    lambda message: print(message, flush=True),
                )
            else:
                journal.snapshot()
                journal.control(args.action)
                print(
                    f"Agent {args.action} requested; current bounded operation may finish before the next checkpoint."
                )
        elif args.command == "research":
            if (
                not args.question.strip()
                or len(args.question) > settings.question_chars
            ):
                raise ConfigurationError(
                    f"Question must contain 1–{settings.question_chars} characters"
                )
            automatic = args.sources is None and args.archive is None
            if automatic and (
                settings.source_search == "explicit"
                or (
                    settings.source_search == "codex"
                    and args.backend in {"ollama", "llama"}
                )
            ):
                raise ConfigurationError(
                    "Provide --sources/--archive, or configure source_search=tools and a search endpoint for local research. Codex search requires an explicitly selected Codex or hybrid backend."
                )
            if automatic and settings.source_search == "tools":
                check_search_configuration(settings)
            if args.sources and args.archive:
                raise ConfigurationError("Choose either --sources or --archive")
            archived_sources = (
                load_archive(args.archive, settings) if args.archive else None
            )
            limit = (
                args.max_calls
                if args.max_calls is not None
                else settings.call_budget(
                    args.mode,
                    automatic,
                    len(archived_sources) if archived_sources is not None else None,
                )
            )
            minimum = (2 if args.mode == "economy" else 4) + (
                settings.source_call_budget if automatic else 0
            )
            if not minimum <= limit <= settings.max_calls:
                raise ConfigurationError(
                    f"--max-calls must be between {minimum} and {settings.max_calls} for this workflow"
                )
            provider, reviewer = research_providers(args.backend, settings)
            job: str | None = None
            try:
                urls = load_manifest(args.sources) if args.sources else []
                job = ledger.create_subscription(
                    args.question[: settings.title_chars], limit
                )
                print(f"Job: {job}", flush=True)
                target = settings.research_root / job
                save_settings(settings, target)
                (target / "request.json").write_text(
                    json.dumps(
                        {
                            "question": args.question,
                            "mode": args.mode,
                            "backend": args.backend,
                            "call_limit": limit,
                        }
                    )
                )
                if automatic:
                    ledger.start(job)
                    if settings.source_search == "tools":
                        runner = StageRunner(
                            ledger,
                            provider,
                            job,
                            target,
                            SYSTEM,
                            lambda message: print(message, flush=True),
                            settings=settings,
                        )
                        urls = resolve_tool_sources(
                            runner,
                            args.question,
                            settings,
                            target,
                            search_runtime(settings, target),
                        )
                    else:
                        searcher = CodexSubscriptionProvider(settings, search=True)
                        try:
                            runner = StageRunner(
                                ledger,
                                searcher,
                                job,
                                target,
                                SYSTEM,
                                lambda message: print(message, flush=True),
                                settings=settings,
                            )
                            urls = resolve_sources(
                                runner, args.question, settings, target
                            )
                        finally:
                            searcher.close()
                sources = (
                    archived_sources
                    if archived_sources is not None
                    else (
                        collect(urls, target / "evidence", settings)
                        if args.no_discovery
                        else discover(
                            urls, args.question, target / "evidence", settings=settings
                        )
                    )
                )
                if args.archive and (args.archive / "discovery.json").is_file():
                    (target / "evidence").mkdir(exist_ok=True)
                    (target / "evidence/discovery.json").write_bytes(
                        (args.archive / "discovery.json").read_bytes()
                    )
                (target / "source-provenance.json").write_text(
                    json.dumps(
                        {
                            "archive": str(args.archive or target / "evidence"),
                            "sources": [source.model_dump() for source in sources],
                        },
                        indent=2,
                    )
                )
                if args.mode == "economy":
                    report = run_economy(
                        ledger,
                        provider,
                        job,
                        args.question,
                        sources,
                        target,
                        progress=lambda message: print(message, flush=True),
                        reviewer=reviewer,
                        refresh=args.refresh,
                        settings=settings,
                        started=automatic,
                    )
                else:
                    report = run_research(
                        ledger,
                        provider,
                        job,
                        args.question,
                        sources,
                        target,
                        progress=lambda message: print(message, flush=True),
                        reviewer=reviewer,
                        settings=settings,
                        started=automatic,
                    )
                print(f"Report: {report.resolve()}")
                print(f"Inspect review and follow-ups: uv run esperia review {job}")
            except Exception:
                if job is not None:
                    state = ledger.review_record(job)["job"]["state"]
                    if state == "queued":
                        ledger.cancel(job)
                    elif state == "running":
                        ledger.block_research(job)
                raise
            finally:
                provider.close()
                if reviewer:
                    reviewer.close()
    except ValidationError:
        if args.command == "library":
            parser.exit(
                2,
                "Invalid notebook input: check note/link field names, types and bounds.\n",
            )
        parser.exit(
            2,
            "Invalid configuration: check field names, types and bounds in your settings/profile.\n",
        )
    except (
        ConfigurationError,
        NotebookError,
        LoopError,
        PolicyError,
        OutputValidationError,
        DiscoveryFailure,
        ToolError,
    ) as error:
        parser.exit(2, f"{error}\n")
    except ProviderFailure as error:
        parser.exit(2, f"{error}. No automatic retry.\n")
    except Exception as error:
        # Avoid printing SDK/HTTP exception bodies, which may echo confidential inputs.
        parser.exit(
            2,
            f"{type(error).__name__}: command stopped. Inspect jobs/calls and saved artifacts; no automatic retry.\n",
        )
