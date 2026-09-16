"""Verify loopback-only inference and real protocol serialization without a model download."""

import json

import httpx
import pytest

from esperia.llama import LlamaProvider
from esperia.subscription import ConfigurationError


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://example.com",
        "http://user:secret@localhost:8080",
        "http://127.0.0.1/other",
        "http://127.0.0.1?key=secret",
    ],
)
def test_nonlocal_or_credential_urls_rejected(url: str) -> None:
    with pytest.raises(ConfigurationError):
        LlamaProvider(url)


def test_local_request_has_schema_limit_and_no_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-to-be-forwarded")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "local-gguf"}]})
        return httpx.Response(
            200,
            json={
                "id": "local-result",
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    provider = LlamaProvider()
    provider.client.close()
    provider.client = httpx.Client(
        base_url=provider.base_url, transport=httpx.MockTransport(handler)
    )
    provider.check_login()
    result = provider.complete(
        "ignored-cloud-model",
        "Instructions",
        json.dumps({"output_schema": {"type": "object"}}),
        100,
    )
    provider.close()
    payload = json.loads(requests[-1].content)
    assert payload["model"] == "local-gguf" and payload["max_tokens"] == 100
    assert payload["response_format"]["schema"] == {"type": "object"}
    assert "authorization" not in requests[-1].headers and "tools" not in payload
    assert result.complete and result.input_tokens == 10


def test_local_failure_does_not_fall_back() -> None:
    provider = LlamaProvider()
    provider.client.close()
    provider.client = httpx.Client(
        base_url=provider.base_url,
        transport=httpx.MockTransport(lambda _: httpx.Response(503)),
    )
    with pytest.raises(ConfigurationError, match="llama-server"):
        provider.check_login()
    provider.close()
