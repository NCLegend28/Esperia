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

from esperia.discovery import DiscoveryFailure, discover
from esperia.economy import run_economy
from esperia.evidence import collect, load_archive
from esperia.execution import OutputValidationError
from esperia.ledger import Ledger, PolicyError
from esperia.llama import LlamaProvider
from esperia.ollama import OllamaProvider
from esperia.owner import inspect_job
from esperia.provider import RATES, ProviderFailure
from esperia.repair import plan_repair, repair_sources, run_repair
from esperia.research import run_research
from esperia.subscription import CodexSubscriptionProvider, ConfigurationError


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
) -> tuple[
    CodexSubscriptionProvider | LlamaProvider | OllamaProvider,
    CodexSubscriptionProvider | None,
]:
    """Select only explicitly requested local/subscription backends; never fall back."""
    if backend == "codex":
        worker: CodexSubscriptionProvider | LlamaProvider | OllamaProvider = (
            CodexSubscriptionProvider()
        )
    elif backend in {"ollama", "ollama-hybrid"}:
        worker = OllamaProvider(
            os.getenv("ESPERIA_OLLAMA_URL", "http://127.0.0.1:11434"),
            os.getenv("ESPERIA_OLLAMA_MODEL", "qwen2.5:7b"),
            integer_setting("ESPERIA_OLLAMA_CONTEXT", 32768, 2048),
            integer_setting("ESPERIA_OLLAMA_TIMEOUT_SECONDS", 900, 30),
        )
    else:
        worker = LlamaProvider(
            os.getenv("ESPERIA_LLAMA_URL", "http://127.0.0.1:8080"),
            os.getenv("ESPERIA_LLAMA_MODEL") or None,
        )
    try:
        worker.check_login()
        reviewer = (
            CodexSubscriptionProvider()
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
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("jobs", help="List persistent jobs")
    doctor = commands.add_parser(
        "doctor", help="Check configuration without generation"
    )
    doctor.add_argument(
        "--backend",
        choices=["codex", "llama", "hybrid", "ollama", "ollama-hybrid"],
        default="codex",
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
    repair_command.add_argument("--no-discovery", action="store_true")
    repair_command.add_argument(
        "--plan",
        action="store_true",
        help="Preview assignments without collection or generation",
    )
    repair_command.add_argument(
        "--backend",
        choices=["codex", "llama", "hybrid", "ollama", "ollama-hybrid"],
        default="ollama",
    )
    repair_command.add_argument(
        "--sources",
        type=Path,
        help="Approved supplemental/replacement URL manifest; otherwise refetch original URLs",
    )
    repair_command.add_argument("--max-calls", type=int, choices=[2, 3], default=2)
    discover_command = commands.add_parser(
        "discover", help="Collect linked filings and PDFs without model calls"
    )
    discover_command.add_argument("question")
    discover_command.add_argument(
        "--sources", type=Path, default=Path("config/quantum-discovery-seeds.json")
    )
    gather = commands.add_parser(
        "collect", help="Archive approved public sources without model calls"
    )
    gather.add_argument(
        "--sources", type=Path, default=Path("config/quantum-sources.json")
    )
    research = commands.add_parser(
        "research", help="Collect sources and run subscription-backed analysis/review"
    )
    research.add_argument("question")
    research.add_argument(
        "--no-discovery",
        action="store_true",
        help="Read only the explicit source manifest",
    )
    research.add_argument(
        "--sources", type=Path, default=Path("config/quantum-discovery-seeds.json")
    )
    research.add_argument(
        "--archive",
        type=Path,
        help="Reuse a verified recent source archive instead of downloading",
    )
    research.add_argument("--max-calls", type=int)
    research.add_argument("--mode", choices=["economy", "deep"], default="economy")
    research.add_argument(
        "--backend",
        choices=["codex", "llama", "hybrid", "ollama", "ollama-hybrid"],
        default="codex",
    )
    research.add_argument(
        "--refresh", action="store_true", help="Bypass validated stage cache"
    )
    args = parser.parse_args()
    load_dotenv(Path(f".env.{args.env}"), override=False)
    if os.getenv("APP_ENV", args.env) != args.env:
        parser.error("APP_ENV does not match selected environment")
    if args.env != "dev":
        parser.error("Cloud environments are not enabled yet")
    try:
        ledger = Ledger(
            Path(os.getenv("ESPERIA_DATABASE", ".local/dev/jobs.sqlite")),
            integer_setting("ESPERIA_MONTHLY_CENTS", 6500, 0),
            integer_setting("ESPERIA_JOB_CENTS", 500, 1),
        )
        if args.command == "doctor":
            provider, reviewer = research_providers(args.backend)
            print(
                json.dumps(
                    {
                        "execution": args.backend,
                        "api_fallback": False,
                        "codex_executable": getattr(provider, "binary", None),
                        "ready": True,
                        "default_max_calls": 3,
                        "models": (
                            [provider.model_name]
                            if isinstance(provider, (LlamaProvider, OllamaProvider))
                            else list(RATES)
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
                    inspect_job(ledger, Path(".local/dev/research"), args.job_id),
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
            root = Path(".local/dev/research")
            plan = plan_repair(ledger, root, args.job_id)
            if args.plan:
                print(json.dumps(plan, indent=2))
            else:
                urls = (
                    load_manifest(args.sources)
                    if args.sources
                    else repair_sources(root, args.job_id)
                )
                provider, reviewer = research_providers(args.backend)
                try:
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
                    )
                    print(f"Report: {report.resolve()}")
                    print(f"Inspect repair: uv run esperia review {report.parent.name}")
                finally:
                    provider.close()
                    if reviewer:
                        reviewer.close()
        elif args.command == "discover":
            target = Path(".local/dev/evidence") / str(uuid4())
            print(f"Discovery archive: {target.resolve()}", flush=True)
            sources = discover(load_manifest(args.sources), args.question, target)
            print(f"Archived {len(sources)} discovered sources: {target.resolve()}")
        elif args.command == "collect":
            target = Path(".local/dev/evidence") / str(uuid4())
            sources = collect(load_manifest(args.sources), target)
            print(f"Archived {len(sources)} sources: {target.resolve()}")
        elif args.command == "research":
            provider, reviewer = research_providers(args.backend)
            if not args.question.strip() or len(args.question) > 4000:
                parser.error("Question must contain 1–4000 characters")
            urls = load_manifest(args.sources) if args.archive is None else []
            limit = (
                args.max_calls
                if args.max_calls is not None
                else (3 if args.mode == "economy" else 16)
            )
            if not 1 <= limit <= 32:
                parser.error("--max-calls must be between 1 and 32")
            job = ledger.create_subscription(
                args.question[:240], min(limit, 3) if args.mode == "economy" else limit
            )
            print(f"Job: {job}", flush=True)
            target = Path(".local/dev/research") / job
            try:
                sources = (
                    load_archive(args.archive)
                    if args.archive
                    else (
                        collect(urls, target / "evidence")
                        if args.no_discovery
                        else discover(urls, args.question, target / "evidence")
                    )
                )
                target.mkdir(parents=True, exist_ok=True)
                if args.archive and (args.archive / "discovery.json").is_file():
                    (target / "evidence").mkdir(exist_ok=True)
                    (target / "evidence/discovery.json").write_bytes(
                        (args.archive / "discovery.json").read_bytes()
                    )
                (target / "request.json").write_text(
                    json.dumps({"question": args.question})
                )
                (target / "source-provenance.json").write_text(
                    json.dumps(
                        {
                            "archive": (
                                str(args.archive)
                                if args.archive
                                else str(target / "evidence")
                            ),
                            "sources": [source.model_dump() for source in sources],
                        },
                        indent=2,
                    )
                )
            except Exception:
                ledger.cancel(job)
                raise
            try:
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
                    )
                print(f"Report: {report.resolve()}")
                print(f"Inspect review and follow-ups: uv run esperia review {job}")
            finally:
                provider.close()
                if reviewer:
                    reviewer.close()
    except (
        ConfigurationError,
        PolicyError,
        OutputValidationError,
        DiscoveryFailure,
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
