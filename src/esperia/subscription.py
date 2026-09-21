"""Official Codex CLI subscription adapter; no API-key or API-credit fallback.

Example: provider = CodexSubscriptionProvider(); provider.check_login()
The CLI manages its own saved ChatGPT login; this code never reads auth tokens.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from esperia.provider import Completion
from esperia.settings import Settings


def subscription_environment() -> dict[str, str]:
    """Pass only runtime essentials; exclude API keys, endpoint overrides and app secrets."""
    allowed = {"HOME", "PATH", "TMPDIR", "LANG", "LC_ALL", "CODEX_HOME", "SYSTEMROOT"}
    return {key: value for key, value in os.environ.items() if key in allowed}


class ConfigurationError(ValueError):
    """Application-authored setup guidance safe to display without exposing secrets."""


def find_codex() -> str:
    """Resolve an explicit executable, PATH installation or installed macOS app bundle.

    Example: set ESPERIA_CODEX_BIN to an absolute executable path for a custom install.
    An invalid explicit override fails rather than silently choosing another installation.
    """
    override = os.getenv("ESPERIA_CODEX_BIN")
    if override is not None:
        candidate = Path(override).expanduser()
        if (
            not candidate.is_absolute()
            or not candidate.is_file()
            or not os.access(candidate, os.X_OK)
        ):
            raise ConfigurationError(
                "ESPERIA_CODEX_BIN must point to an existing absolute executable path. Correct it in .env.dev."
            )
        return str(candidate)
    binary = shutil.which("codex")
    if binary:
        return binary
    for folder in (Path("/Applications"), Path.home() / "Applications"):
        for application in ("Codex.app", "ChatGPT.app"):
            candidate = folder / application / "Contents/Resources/codex"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    raise ConfigurationError(
        "Codex was not found on PATH or in an installed macOS app. Install the official Codex CLI or set ESPERIA_CODEX_BIN in .env.dev, then sign in with ChatGPT."
    )


class CodexSubscriptionProvider:
    """Execute bounded stages using saved ChatGPT authentication and read-only tools."""

    billing_mode = "subscription"

    def __init__(self, settings: Settings | None = None, search: bool = False) -> None:
        self.settings = settings or Settings()
        self.search = search
        self.cache_identity = self.settings.model_dump_json() + str(search)
        self.binary = find_codex()

    def check_login(self) -> None:
        """Confirm subscription login without printing credentials or changing auth."""
        try:
            result = subprocess.run(
                [self.binary, "login", "status"],
                capture_output=True,
                text=True,
                env=subscription_environment(),
                timeout=self.settings.login_timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ConfigurationError(
                "Codex login status could not be checked. Run `uv run esperia doctor` after confirming the configured Codex executable works."
            ) from None
        if (
            result.returncode
            or "Logged in using ChatGPT" not in result.stdout + result.stderr
        ):
            raise ConfigurationError(
                f'Codex is not signed in with ChatGPT. Run "{self.binary}" login and choose ChatGPT, then retry. API-key authentication is not accepted.'
            )

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        """Run one stage; timeout/usage limits stop work without switching billing paths.

        The output-token target is advisory in the CLI. Runtime and call counts are
        bounded; subscription quotas are enforced by Codex, not inferred from dollars.
        """
        self.check_login()
        if len(prompt.encode()) > self.settings.prompt_bytes:
            raise ValueError("Research context is too large")
        with TemporaryDirectory(prefix="esperia-codex-") as temporary:
            folder = Path(temporary)
            schema = folder / "schema.json"
            schema.write_text(json.dumps(json.loads(prompt)["output_schema"]))
            output = folder / "answer.json"
            command = [
                self.binary,
                "exec",
                "--ignore-user-config",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--json",
                "--disable",
                "shell_tool",
                "--disable",
                "multi_agent",
                "--disable",
                "apps",
                "-c",
                'forced_login_method="chatgpt"',
                "-c",
                'model_provider="openai"',
                "-c",
                'web_search="live"' if self.search else 'web_search="disabled"',
                "-c",
                'approval_policy="never"',
                "-c",
                f'model_reasoning_effort="{self.settings.reasoning_effort}"',
                "--model",
                model,
                "--cd",
                temporary,
                "--output-schema",
                str(schema),
                "--output-last-message",
                str(output),
                "-",
            ]
            result = subprocess.run(
                command,
                input=instructions
                + f"\nAim for at most {maximum} output tokens.\n"
                + prompt,
                capture_output=True,
                text=True,
                env=subscription_environment(),
                timeout=self.settings.codex_timeout,
                check=False,
            )
            if result.returncode or not output.exists():
                raise RuntimeError(
                    "Codex subscription stage stopped; check login or usage limits. No API fallback."
                )
            incoming = outgoing = 0
            thread_id = "codex-subscription"
            completed = False
            for line in result.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "thread.started":
                    thread_id = event.get("thread_id", thread_id)
                if event.get("type") == "turn.completed":
                    usage = event.get("usage", {})
                    incoming += usage.get("input_tokens", 0)
                    outgoing += usage.get("output_tokens", 0)
                    completed = True
            return Completion(
                output.read_text(), incoming, outgoing, thread_id, completed
            )

    def close(self) -> None:
        """No persistent subprocess or credential handle is retained."""
