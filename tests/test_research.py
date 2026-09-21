"""Verify actual workflow boundaries using deterministic provider responses."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from esperia.evidence import Source, collect, validate_url
from esperia.ledger import Ledger, PolicyError
from esperia.provider import Completion, OpenAIProvider, reservation_cents
from esperia.research import CHECKS, run_research


class ScriptedProvider:
    """Test double returns schema-conforming outputs; never used in product commands."""

    def __init__(
        self, passed: bool = True, bad_quote: bool = False, fail: bool = False
    ):
        self.passed, self.bad_quote, self.fail = passed, bad_quote, fail
        self.calls = 0

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        self.calls += 1
        if self.fail:
            raise TimeoutError("uncertain transport result")
        request = json.loads(prompt)
        kind = request["output_schema"]["title"]
        body: dict[str, Any]
        if kind == "Plan":
            body = {"questions": ["What is evidenced?"], "missing_inputs": []}
        elif kind in {"Notes", "SelectedNotes"}:
            body = {
                "claims": [
                    {
                        "statement": "A supported test claim",
                        "source_id": "S1",
                        "quote": (
                            "This quote was fabricated entirely."
                            if self.bad_quote
                            else "The company reported revenue of ten dollars."
                        ),
                    }
                ],
                "limitations": [],
            }
        elif kind == "Draft":
            body = {
                "title": "Test report",
                "sections": [
                    {"title": "Evidence", "text": "Test only.", "source_ids": ["S1"]}
                ],
                "missing_evidence": [],
            }
        else:
            body = {
                "checks": [
                    {
                        "name": key,
                        "passed": self.passed,
                        "explanation": "Test criterion",
                    }
                    for key in CHECKS
                ],
                "corrections": [],
            }
        if kind == "SelectedNotes":
            task = json.loads(request["task"])
            body["claims"] = [
                {
                    "statement": "A supported test claim",
                    "excerpt_id": (
                        "invented" if self.bad_quote else task["excerpts"][0]["id"]
                    ),
                }
            ]
        return Completion(json.dumps(body), 100, 100, f"response-{self.calls}", True)


def source() -> Source:
    return Source(
        id="S1",
        url="https://investors.ionq.com/financials/quarterly-results/",
        fetched_at="2026-09-13T00:00:00Z",
        sha256="a" * 64,
        truncated=False,
        text="The company reported revenue of ten dollars.",
    )


def test_success_awaits_owner_and_persists_costs(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 6500)
    job = ledger.create("Test", 500)
    report = run_research(
        ledger,
        ScriptedProvider(),
        job,
        "Research",
        [source()],
        tmp_path / "run",
        lambda _: None,
    )
    assert report.exists()
    row = ledger.list_jobs()[0]
    assert row["state"] == "awaiting_owner" and row["reserved"] == 0
    assert row["actual"] > 0
    assert len(ledger.list_calls(job)) == 4


def test_failed_reviews_stop_after_two_revisions(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 6500)
    job = ledger.create("Test", 500)
    provider = ScriptedProvider(passed=False)
    report = run_research(
        ledger, provider, job, "Research", [source()], tmp_path / "run", lambda _: None
    )
    assert provider.calls == 8
    assert "acceptance checks failed" in report.read_text()
    assert ledger.list_jobs()[0]["state"] == "blocked"


def test_fabricated_quote_blocks_report(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 6500)
    job = ledger.create("Test", 500)
    with pytest.raises(ValueError, match=r"claims\.0\.excerpt_id"):
        run_research(
            ledger,
            ScriptedProvider(bad_quote=True),
            job,
            "Research",
            [source()],
            tmp_path / "run",
            lambda _: None,
        )
    assert ledger.list_jobs()[0]["state"] == "blocked"
    assert not (tmp_path / "run/report.md").exists()


def test_unknown_charge_survives_failure_and_cannot_be_released(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 6500)
    job = ledger.create("Test", 500)
    with pytest.raises(RuntimeError, match="uncertain"):
        run_research(
            ledger,
            ScriptedProvider(fail=True),
            job,
            "Research",
            [source()],
            tmp_path / "run",
            lambda _: None,
        )
    assert ledger.list_jobs()[0]["reserved"] > 0
    assert ledger.list_calls(job)[0]["state"] == "uncertain"
    with pytest.raises(PolicyError):
        ledger.cancel(job)
    with pytest.raises(PolicyError):
        ledger.complete_research(job, True)


def test_insufficient_budget_prevents_provider_dispatch(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 6500)
    job = ledger.create("Test", 1)
    provider = ScriptedProvider()
    with pytest.raises(PolicyError):
        run_research(
            ledger,
            provider,
            job,
            "Research",
            [source()],
            tmp_path / "run",
            lambda _: None,
        )
    assert provider.calls == 0


def test_metered_calls_cannot_be_overwritten_or_replayed(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "jobs.sqlite", 500)
    job = ledger.create("Test", 100)
    ledger.start(job)
    call = ledger.reserve_call(job, "plan", "gpt-6-astra", 80)
    with pytest.raises(PolicyError):
        ledger.reserve_call(job, "other", "gpt-6-astra", 30)
    with pytest.raises(PolicyError):
        ledger.finish(job, 0)
    ledger.settle_call(call, 20, "response")
    with pytest.raises(PolicyError):
        ledger.reserve_call(job, "plan", "gpt-6-astra", 10)
    with pytest.raises(PolicyError):
        ledger.settle_call(call, 0, "response")


@pytest.mark.parametrize(
    "url",
    [
        "http://investors.ionq.com/",
        "https://127.0.0.1/",
        "https://user:pass@investors.ionq.com/",
        "https://investors.ionq.com:8443/",
    ],
)
def test_source_policy_rejects_unapproved_destinations(url: str) -> None:
    with pytest.raises(ValueError):
        validate_url(url)


def test_collector_never_follows_redirects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_client = httpx.Client

    def client(**kwargs: Any) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(
            **kwargs,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(302, headers={"location": "http://127.0.0.1/"})
            ),
        )

    monkeypatch.setattr(httpx, "Client", client)
    with pytest.raises(httpx.HTTPStatusError):
        collect(["https://investors.ionq.com/"], tmp_path)


def test_provider_wire_request_is_bounded_and_usage_observed() -> None:
    observed: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "created_at": 1,
                "model": "gpt-5.6-terra",
                "object": "response",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_test",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "text": "{}", "annotations": []}
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            },
        )

    provider = OpenAIProvider("test-not-a-real-key")
    provider.client.close()
    from openai import OpenAI

    provider.client = OpenAI(
        api_key="test-not-a-real-key",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = provider.complete("gpt-5.6-terra", "System", "Question", 100)
    provider.close()
    assert result.complete and result.input_tokens == 10 and result.output_tokens == 20
    assert observed[0]["max_output_tokens"] == 100
    assert observed[0]["store"] is False
    assert "tools" not in observed[0]


def test_context_limit_prevents_unbounded_request() -> None:
    with pytest.raises(ValueError):
        reservation_cents("gpt-6-astra", "", "x" * 180001, 100)


def test_credit_rejection_releases_job_budget(tmp_path: Path) -> None:
    from esperia.provider import ProviderFailure

    class RejectedProvider:
        def complete(
            self, model: str, instructions: str, prompt: str, maximum: int
        ) -> Completion:
            raise ProviderFailure(429, "credit_balance_exhausted", True)

    ledger = Ledger(tmp_path / "jobs.sqlite", 500)
    job = ledger.create("Test", 100)
    with pytest.raises(ProviderFailure):
        run_research(
            ledger,
            RejectedProvider(),
            job,
            "Research",
            [source()],
            tmp_path / "run",
            lambda _: None,
        )
    row = ledger.list_jobs()[0]
    assert row["reserved"] == 0 and row["actual"] == 0 and row["state"] == "blocked"
    error = json.loads((tmp_path / "run/plan-error.json").read_text())
    assert error["code"] == "credit_balance_exhausted"


def test_archive_tampering_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from esperia.evidence import load_archive

    real_client = httpx.Client

    def client(**kwargs: Any) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(
            **kwargs,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    headers={"content-type": "text/html"},
                    text="<p>Public evidence with sufficient text for validation. "
                    + "data " * 30
                    + "</p>",
                )
            ),
        )

    monkeypatch.setattr(httpx, "Client", client)
    sources = collect(["https://www.ionq.com/"], tmp_path)
    assert load_archive(tmp_path)[0].sha256 == sources[0].sha256
    manifest = json.loads((tmp_path / "sources.json").read_text())
    manifest[0]["text"] = "Fabricated extracted evidence"
    (tmp_path / "sources.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="modified"):
        load_archive(tmp_path)
