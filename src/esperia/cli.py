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

from esperia.evidence import collect, load_archive
from esperia.ledger import Ledger, PolicyError
from esperia.provider import RATES, ProviderFailure
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


def main() -> None:
    """Dispatch owner commands with environment isolation and redacted errors."""
    parser = argparse.ArgumentParser(description="Esperia research console")
    parser.add_argument(
        "--env", choices=["dev", "staging", "production"], default="dev"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("jobs", help="List persistent jobs")
    commands.add_parser("doctor", help="Check configuration without making paid calls")
    calls = commands.add_parser("calls", help="Inspect stages/models/costs for a job")
    calls.add_argument("job_id")
    create = commands.add_parser("create", help="Reserve a job; does not execute it")
    create.add_argument("title")
    create.add_argument("--budget-cents", type=int, required=True)
    create.add_argument("--approval", action="store_true")
    for action in ["approve", "cancel"]:
        command = commands.add_parser(action)
        command.add_argument("job_id")
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
        "--sources", type=Path, default=Path("config/quantum-sources.json")
    )
    research.add_argument(
        "--archive",
        type=Path,
        help="Reuse a verified recent source archive instead of downloading",
    )
    research.add_argument("--max-calls", type=int, default=16)
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
            provider = CodexSubscriptionProvider()
            provider.check_login()
            print(
                json.dumps(
                    {
                        "execution": "codex_chatgpt_subscription",
                        "api_fallback": False,
                        "codex_executable": provider.binary,
                        "login": "ChatGPT subscription",
                        "default_max_calls": 16,
                        "models": list(RATES),
                        "generation_checked": False,
                        "cloud_deployed": False,
                    },
                    indent=2,
                )
            )
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
        elif args.command == "collect":
            target = Path(".local/dev/evidence") / str(uuid4())
            sources = collect(load_manifest(args.sources), target)
            print(f"Archived {len(sources)} sources: {target.resolve()}")
        elif args.command == "research":
            provider = CodexSubscriptionProvider()
            provider.check_login()
            if not args.question.strip() or len(args.question) > 4000:
                parser.error("Question must contain 1–4000 characters")
            urls = load_manifest(args.sources) if args.archive is None else []
            job = ledger.create_subscription(args.question[:240], args.max_calls)
            print(f"Job: {job}", flush=True)
            target = Path(".local/dev/research") / job
            try:
                sources = (
                    load_archive(args.archive)
                    if args.archive
                    else collect(urls, target / "evidence")
                )
                target.mkdir(parents=True, exist_ok=True)
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
                report = run_research(
                    ledger,
                    provider,
                    job,
                    args.question,
                    sources,
                    target,
                    progress=lambda message: print(message, flush=True),
                )
                print(f"Report: {report.resolve()}")
            finally:
                provider.close()
    except (ConfigurationError, PolicyError) as error:
        parser.exit(2, f"{error}\n")
    except ProviderFailure as error:
        parser.exit(2, f"{error}. No automatic retry.\n")
    except Exception as error:
        # Avoid printing SDK/HTTP exception bodies, which may echo confidential inputs.
        parser.exit(
            2,
            f"{type(error).__name__}: command stopped. Inspect jobs/calls and saved artifacts; no automatic retry.\n",
        )
