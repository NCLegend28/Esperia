"""Subscription execution must not inherit API credentials or dollar billing."""

from pathlib import Path

import pytest

from esperia.ledger import Ledger, PolicyError
from esperia.subscription import subscription_environment


def test_api_credentials_are_not_passed_to_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("CODEX_API_KEY", "test-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid")
    env = subscription_environment()
    assert "OPENAI_API_KEY" not in env and "CODEX_API_KEY" not in env
    assert "OPENAI_BASE_URL" not in env


def test_subscription_calls_have_zero_dollar_cost_and_bounded_count(
    tmp_path: Path,
) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("Research", 1)
    ledger.start(job)
    call = ledger.reserve_subscription_call(job, "plan", "gpt-6-astra")
    ledger.settle_call(call, 0, "subscription-result")
    with pytest.raises(PolicyError):
        ledger.reserve_subscription_call(job, "writer", "gpt-6-astra")
    ledger.complete_research(job, True)
    assert ledger.list_jobs()[0]["actual"] == 0
    assert ledger.list_jobs()[0]["reserved"] == 0


def test_app_bundle_is_found_when_terminal_path_has_no_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import esperia.subscription as module

    monkeypatch.delenv("ESPERIA_CODEX_BIN", raising=False)
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    expected = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
    monkeypatch.setattr(Path, "is_file", lambda self: self == expected)
    monkeypatch.setattr(module.os, "access", lambda path, mode: path == expected)
    assert module.find_codex() == str(expected)


def test_invalid_explicit_binary_is_not_silently_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from esperia.subscription import ConfigurationError, find_codex

    monkeypatch.setenv("ESPERIA_CODEX_BIN", "/does/not/exist")
    with pytest.raises(ConfigurationError, match="ESPERIA_CODEX_BIN"):
        find_codex()


def test_failed_preflight_explains_login_without_creating_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    from esperia.cli import main
    from esperia.subscription import CodexSubscriptionProvider, ConfigurationError

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ESPERIA_DATABASE", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setattr(
        CodexSubscriptionProvider, "__init__", lambda self, *args, **kwargs: None
    )

    def reject(self: CodexSubscriptionProvider) -> None:
        raise ConfigurationError("Sign in with ChatGPT")

    monkeypatch.setattr(CodexSubscriptionProvider, "check_login", reject)
    monkeypatch.setattr(sys, "argv", ["esperia", "research", "Quantum research"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "Sign in with ChatGPT" in capsys.readouterr().err
    assert Ledger(tmp_path / "jobs.sqlite", 6500).list_jobs() == []


def test_invalid_numeric_setting_is_actionable_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from esperia.cli import integer_setting
    from esperia.subscription import ConfigurationError

    monkeypatch.setenv("ESPERIA_MONTHLY_CENTS", "private-value")
    with pytest.raises(ConfigurationError) as error:
        integer_setting("ESPERIA_MONTHLY_CENTS", 6500, 0)
    assert "ESPERIA_MONTHLY_CENTS" in str(error.value)
    assert "private-value" not in str(error.value)
