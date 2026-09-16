"""Exercise native Ollama requests and prevent remote-model execution."""

import json

import httpx
import pytest

from esperia.ollama import OllamaProvider
from esperia.subscription import ConfigurationError


def provider_for(
    remote: bool = False, missing: bool = False
) -> tuple[OllamaProvider, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": (
                        []
                        if missing
                        else [{"name": "qwen2.5:7b", "digest": "sha256-local"}]
                    )
                },
            )
        if request.url.path == "/api/show":
            return httpx.Response(
                200,
                json={
                    "remote_host": "https://ollama.com" if remote else "",
                    "tensors": [{"name": "weights"}],
                    "capabilities": ["completion"],
                    "model_info": {"qwen.context_length": 32768},
                },
            )
        return httpx.Response(
            200,
            json={
                "message": {"content": '{"ok": true}'},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 10,
                "eval_count": 4,
            },
        )

    provider = OllamaProvider()
    provider.client.close()
    provider.client = httpx.Client(
        base_url=provider.base_url, transport=httpx.MockTransport(handler)
    )
    return provider, requests


def test_native_schema_and_digest() -> None:
    provider, requests = provider_for()
    provider.check_login()
    result = provider.complete(
        "ignored", "system", json.dumps({"output_schema": {"type": "object"}}), 99
    )
    payload = json.loads(requests[-1].content)
    assert payload["model"] == "qwen2.5:7b"
    assert payload["format"] == {"type": "object"}
    assert payload["options"]["num_predict"] == 99
    assert payload["options"]["num_ctx"] == 32768
    assert payload["stream"] is False
    assert "authorization" not in requests[-1].headers
    assert "sha256-local" in provider.cache_identity
    assert result.complete and result.output_tokens == 4
    provider.close()


@pytest.mark.parametrize("remote,missing", [(True, False), (False, True)])
def test_remote_or_missing_model_never_generates(remote: bool, missing: bool) -> None:
    provider, requests = provider_for(remote, missing)
    with pytest.raises(ConfigurationError):
        provider.check_login()
    assert all(r.url.path != "/api/chat" for r in requests)
    provider.close()


def test_cloud_tag_rejected() -> None:
    with pytest.raises(ConfigurationError):
        OllamaProvider(model="kimi-k2.5:cloud")


def test_excess_context_rejected() -> None:
    provider, _ = provider_for()
    provider.context = 65536
    with pytest.raises(ConfigurationError, match="context capacity"):
        provider.check_login()
    provider.close()


def test_long_response_timeout_and_short_connect_timeout() -> None:
    provider = OllamaProvider(timeout_seconds=900)
    assert provider.client.timeout.read == 900
    assert provider.client.timeout.connect == 10
    provider.close()


def test_timeout_is_distinct_from_http_failure() -> None:
    provider, _ = provider_for()
    provider.check_login()
    provider.client.close()

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private response details", request=request)

    provider.client = httpx.Client(
        base_url=provider.base_url, transport=httpx.MockTransport(timeout)
    )
    with pytest.raises(ConfigurationError, match="timed out") as error:
        provider.complete(
            "ignored", "instructions", json.dumps({"output_schema": {}}), 100
        )
    assert "900s" in str(error.value) and "private response" not in str(error.value)
    provider.client.close()
    provider.client = httpx.Client(
        base_url=provider.base_url,
        transport=httpx.MockTransport(lambda _: httpx.Response(500)),
    )
    with pytest.raises(ConfigurationError, match="HTTP 500"):
        provider.complete(
            "ignored", "instructions", json.dumps({"output_schema": {}}), 100
        )
    provider.close()


@pytest.mark.parametrize("seconds", [0, 29, 3601])
def test_invalid_local_timeout_refused(seconds: int) -> None:
    with pytest.raises(ConfigurationError, match="TIMEOUT_SECONDS"):
        OllamaProvider(timeout_seconds=seconds)
