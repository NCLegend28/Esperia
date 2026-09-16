"""llama.cpp chat-completions adapter for an existing loopback server.

Example: provider = LlamaProvider("http://127.0.0.1:8080"); provider.check_login()
No cloud provider, credential forwarding, automatic download, or fallback is used.
"""

import json
from urllib.parse import urlsplit

import httpx

from esperia.provider import Completion
from esperia.subscription import ConfigurationError


def loopback_url(base_url: str) -> str:
    """Validate an owner-managed inference endpoint without forwarding credentials."""
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/", "/v1", "/v1/"}
    ):
        raise ConfigurationError(
            "Local inference requires a loopback URL, without credentials"
        )
    return base_url.rstrip("/").removesuffix("/v1")


class LlamaProvider:
    """Connect to an owner-managed local llama-server instance."""

    billing_mode = "local"

    def __init__(
        self, base_url: str = "http://127.0.0.1:8080", model: str | None = None
    ):
        self.base_url = loopback_url(base_url)
        self.model_name = model or ""
        self.cache_identity = self.base_url
        self.client = httpx.Client(
            base_url=self.base_url, timeout=240, follow_redirects=False, trust_env=False
        )

    def check_login(self) -> None:
        """Check server health/model metadata; local inference needs no subscription login."""
        try:
            response = self.client.get("/v1/models", timeout=10)
            response.raise_for_status()
            models = response.json()["data"]
            if not models or (not self.model_name and len(models) != 1):
                raise ConfigurationError(
                    "Choose ESPERIA_LLAMA_MODEL from your server's /v1/models list"
                )
            selected = (
                next((m for m in models if m["id"] == self.model_name), None)
                if self.model_name
                else models[0]
            )
            if selected is None:
                raise ConfigurationError(
                    "ESPERIA_LLAMA_MODEL is not served by this llama-server"
                )
            self.model_name = selected["id"]
            self.cache_identity = self.base_url + json.dumps(selected, sort_keys=True)
        except (httpx.HTTPError, KeyError, ValueError) as error:
            if isinstance(error, ConfigurationError):
                raise
            raise ConfigurationError(
                "Cannot reach a ready llama-server. Start your existing server on loopback and check ESPERIA_LLAMA_URL."
            ) from None

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        """Request schema-constrained JSON with an explicit generation token limit."""
        if not self.model_name:
            raise ConfigurationError("Check the local server before starting research")
        schema = json.loads(prompt)["output_schema"]
        try:
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": maximum,
                    "temperature": 0.1,
                    "stream": False,
                    "response_format": {"type": "json_object", "schema": schema},
                },
            )
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return Completion(
                choice["message"]["content"],
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                data.get("id", "llama-local"),
                choice.get("finish_reason") == "stop",
            )
        except httpx.HTTPError:
            raise ConfigurationError(
                "Local generation failed. Check llama-server logs and available context/memory; no cloud fallback was attempted."
            ) from None

    def close(self) -> None:
        """Release local HTTP resources."""
        self.client.close()
