"""Cross-domain, configuration and pinned-network regression tests; no live services."""

import json
import socket
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from test_economy import Worker
from test_research import source

from esperia import cli
from esperia.discovery import link_score
from esperia.economy import run_economy
from esperia.evidence import validate_url
from esperia.execution import OutputValidationError, StageRunner
from esperia.ledger import Ledger
from esperia.network import PublicTransport
from esperia.provider import Completion
from esperia.settings import Profile, Settings, load_settings
from esperia.sourcing import resolve_sources


def test_public_sources_are_not_sector_restricted() -> None:
    for url in (
        "https://investor.nexteraenergy.com/",
        "https://www.nasa.gov/",
        "https://www.nature.com/",
    ):
        validate_url(url)
    with pytest.raises(ValueError, match="host policy"):
        validate_url(
            "https://www.nasa.gov/", Settings(allowed_hosts=["www.nature.com"])
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://localhost/",
        "https://metadata.internal/",
        "https://user:secret@example.com",
        "https://example.com:1234/",
        "https://example.com/\\evil",
    ],
)
def test_public_url_invariants(url: str) -> None:
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize(
    "addresses", [["127.0.0.1"], ["169.254.169.254"], ["10.1.2.3"], ["8.8.8.8", "::1"]]
)
def test_dns_private_and_mixed_answers_never_connect(
    monkeypatch: pytest.MonkeyPatch, addresses: list[str]
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses
        ],
    )
    transport = PublicTransport(Settings())
    transport.inner = httpx.MockTransport(lambda request: pytest.fail("Private address was contacted"))  # type: ignore[assignment]
    with pytest.raises(ValueError, match="public addresses"):
        transport.handle_request(httpx.Request("GET", "https://example.com/"))
    transport.close()


def test_dns_is_pinned_while_host_and_tls_name_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions: list[str] = []

    def resolve(host: str, *args: Any, **kwargs: Any) -> list[Any]:
        resolutions.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    transport = PublicTransport(Settings())

    def request(req: httpx.Request) -> httpx.Response:
        assert req.url.host == "8.8.8.8"
        assert req.headers["host"] == "example.com"
        assert req.extensions["sni_hostname"] == "example.com"
        return httpx.Response(200, text="ok")

    transport.inner = httpx.MockTransport(request)  # type: ignore[assignment]
    response = transport.handle_request(
        httpx.Request("GET", "https://example.com/report")
    )
    assert response.status_code == 200
    assert resolutions == ["example.com"]
    transport.close()


def test_energy_terms_outrank_unrelated_financial_documents() -> None:
    query = "Compare oil gas wind and LNG"
    assert link_score("/wind", "Gas LNG wind", query) > link_score(
        "/annual-report", "Annual financial report", query
    )
    assert link_score("/research", "énergie solaire", "énergie solaire") > 0


def test_settings_are_validated_and_paths_are_workspace_relative(
    tmp_path: Path,
) -> None:
    config = tmp_path / "esperia.json"
    config.write_text(
        json.dumps(
            {
                "data_root": "data",
                "analyst_model": "chosen-model",
                "profile": {"name": "science", "checks": ["scope", "replicability"]},
            }
        )
    )
    settings = load_settings(config)
    assert settings.data_root == tmp_path / "data"
    assert settings.analyst_model == "chosen-model"
    assert settings.profile.checks == ["scope", "replicability"]
    for value in (
        {"unknown": True},
        {"requests": 1},
        {"excerpt_stride": 501},
        {"profile": {"checks": ["same", "same"]}},
    ):
        with pytest.raises(ValidationError):
            Settings.model_validate(value)


def test_model_and_profile_changes_invalidate_stage_cache(tmp_path: Path) -> None:
    class ConfiguredWorker(Worker):
        def __init__(self) -> None:
            super().__init__()
            self.models: list[str] = []

        def complete(
            self, model: str, instructions: str, prompt: str, maximum: int
        ) -> Completion:
            self.models.append(model)
            response = super().complete(model, instructions, prompt, maximum)
            task = json.loads(json.loads(prompt)["task"])
            body = json.loads(response.text)
            if "checks" in body:
                body["checks"] = [
                    {"name": c, "passed": True, "explanation": "Checked"}
                    for c in task["checks"]
                ]
            return Completion(json.dumps(body), 1, 1, response.response_id, True)

    worker = ConfiguredWorker()
    settings = Settings(analyst_model="worker-A", reviewer_model="review-A")
    ledger = Ledger(tmp_path / "jobs.sqlite", 0, settings=settings)

    def run(settings: Settings) -> None:
        job = ledger.create_subscription("Research", 3)
        run_economy(
            ledger,
            worker,
            job,
            "Research",
            [source()],
            tmp_path / job,
            lambda _: None,
            settings=settings,
        )

    run(settings)
    run(settings)
    assert worker.models == ["worker-A", "review-A"]
    run(settings.model_copy(update={"reviewer_model": "review-B"}))
    assert worker.models[-1] == "review-B"
    run(
        settings.model_copy(
            update={
                "profile": Profile(name="science", checks=["scope", "replicability"])
            }
        )
    )
    assert worker.calls == 6


class SearchWorker:
    billing_mode = "subscription"

    def __init__(self, fail: bool = False):
        self.calls = 0
        self.fail = fail

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        self.calls += 1
        if self.fail:
            raise TimeoutError("unknown outcome")
        question = json.loads(json.loads(prompt)["task"])["question"]
        assert "energy" in question
        return Completion(
            json.dumps(
                {
                    "scope": "Representative energy businesses over the requested horizon",
                    "sources": [
                        {
                            "url": "https://investor.nexteraenergy.com/",
                            "entity": "Energy company",
                            "relevance": "Energy research",
                        }
                    ],
                    "limitations": ["Representative, not exhaustive"],
                }
            ),
            1,
            1,
            "search-1",
            True,
        )

    def close(self) -> None:
        pass


def test_source_resolution_is_question_driven_and_metered(tmp_path: Path) -> None:
    settings = Settings()
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.create_subscription("energy", 3)
    ledger.start(job)
    runner = StageRunner(
        ledger, SearchWorker(), job, tmp_path, "system", lambda _: None
    )
    urls = resolve_sources(runner, "Compare energy", settings, tmp_path)
    assert urls == ["https://investor.nexteraenergy.com/"]
    assert len(ledger.list_calls(job)) == 1
    assert (tmp_path / "source-scope.json").exists()


@pytest.mark.parametrize("failed", [False, True])
def test_cli_auto_sources_and_uncertain_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    class ConsoleWorker(Worker):
        def close(self) -> None:
            pass

    worker = ConsoleWorker()
    searcher = SearchWorker(failed)
    captured: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ESPERIA_DATABASE", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setattr(
        "sys.argv", ["esperia", "research", "Compare energy", "--backend", "codex"]
    )
    monkeypatch.setattr(cli, "research_providers", lambda *args: (worker, None))
    monkeypatch.setattr(
        cli, "CodexSubscriptionProvider", lambda *args, **kwargs: searcher
    )

    def collect(urls: list[str], *args: Any, **kwargs: Any) -> list[Any]:
        captured.append(urls)
        return [source().model_copy(update={"url": urls[0]})]

    monkeypatch.setattr(cli, "discover", collect)
    if failed:
        with pytest.raises(SystemExit):
            cli.main()
    else:
        cli.main()
    ledger = Ledger(tmp_path / "jobs.sqlite", 0)
    job = ledger.list_jobs()[0]
    assert searcher.calls == 1
    if failed:
        assert job["state"] == "blocked"
        assert ledger.list_calls(job["id"])[0]["state"] == "uncertain"
        assert not captured
        assert worker.calls == 0
    else:
        assert captured == [["https://investor.nexteraenergy.com/"]]
        assert job["state"] == "awaiting_owner"
        assert len(ledger.list_calls(job["id"])) == 3
        report = tmp_path / ".local/dev/research" / job["id"] / "report.md"
        assert "Representative energy" in report.read_text()


def test_local_only_without_sources_never_uses_cloud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv", ["esperia", "research", "Compare energy", "--backend", "ollama"]
    )
    monkeypatch.setattr(
        cli, "research_providers", lambda *a: pytest.fail("Provider instantiated")
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_prompt_budget_failure_does_not_reserve_a_call(tmp_path: Path) -> None:
    from esperia.economy import Analysis

    settings = Settings(prompt_bytes=1000)
    ledger = Ledger(tmp_path / "jobs.sqlite", 0, settings=settings)
    job = ledger.create_subscription("Research", 3)
    ledger.start(job)
    worker = Worker()
    runner = StageRunner(ledger, worker, job, tmp_path, "", lambda _: None)
    with pytest.raises(OutputValidationError):
        runner.invoke("analysis", "test", "x" * 2000, Analysis)
    assert worker.calls == 0
    assert ledger.list_calls(job) == []


def test_custom_projection_archive_remains_verifiable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from esperia.evidence import collect, load_archive

    real_client = httpx.Client

    def client(**kwargs: Any) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(
            **kwargs,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    headers={"content-type": "text/plain"},
                    text="Public energy evidence " * 100,
                )
            ),
        )

    monkeypatch.setattr(httpx, "Client", client)
    collected = collect(
        ["https://energy.example.com/"], tmp_path, Settings(source_chars=600)
    )
    assert len(collected[0].text) == 600
    assert load_archive(tmp_path) == collected
    with pytest.raises(ValueError, match="host policy"):
        load_archive(tmp_path, Settings(allowed_hosts=["www.nasa.gov"]))
    data = json.loads((tmp_path / "sources.json").read_text())
    data[0]["text"] = data[0]["text"][:100]
    (tmp_path / "sources.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="modified"):
        load_archive(tmp_path)


def test_config_command_from_another_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = workspace / "esperia.json"
    config.write_text(
        json.dumps({"data_root": "data", "analyst_model": "custom-model"})
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ESPERIA_DATABASE", raising=False)
    monkeypatch.setattr("sys.argv", ["esperia", "--config", str(config), "config"])
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert result["data_root"] == str(workspace / "data")
    assert result["analyst_model"] == "custom-model"
    assert not (workspace / "data").exists()


def test_archive_budget_uses_actual_source_count() -> None:
    assert Settings().call_budget("deep", source_count=24) == 31
    assert Settings(revision_rounds=1).call_budget("deep", source_count=2) == 7


@pytest.mark.parametrize("search", [False, True])
def test_codex_search_capability_is_explicit_and_settings_applied(
    monkeypatch: pytest.MonkeyPatch, search: bool
) -> None:
    import subprocess

    from esperia import subscription

    monkeypatch.setattr(subscription, "find_codex", lambda: "/test/codex")
    settings = Settings(reasoning_effort="high", codex_timeout=333)
    provider = subscription.CodexSubscriptionProvider(settings, search=search)
    monkeypatch.setattr(provider, "check_login", lambda: None)

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert ('web_search="live"' if search else 'web_search="disabled"') in command
        assert 'model_reasoning_effort="high"' in command
        assert command[command.index("--model") + 1] == "chosen-model"
        assert "shell_tool" in command and "apps" in command
        assert kwargs["timeout"] == 333
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text("{}")
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            ),
            "",
        )

    monkeypatch.setattr(subscription.subprocess, "run", run)
    result = provider.complete(
        "chosen-model", "system", json.dumps({"output_schema": {"type": "object"}}), 100
    )
    assert result.complete
