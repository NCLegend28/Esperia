"""Native Ollama inference using installed local weights only.

Example: provider = OllamaProvider(model="qwen2.5:7b"); provider.check_login()
No model downloads, remote models, or subscription fallback are performed.
"""

import json

import httpx

from esperia.llama import loopback_url
from esperia.provider import Completion
from esperia.settings import Settings
from esperia.subscription import ConfigurationError


class OllamaProvider:
    """Use schema-constrained generation against the owner's local Ollama server."""

    billing_mode = "local"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        context: int | None = None,
        timeout_seconds: int | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or Settings()
        base_url = base_url if base_url is not None else self.settings.ollama_url
        model = model if model is not None else self.settings.ollama_model
        context = context if context is not None else self.settings.ollama_context
        timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else self.settings.ollama_timeout
        )
        self.base_url = loopback_url(base_url)
        if not model or "cloud" in model.lower() or context < 2048:
            raise ConfigurationError(
                "Choose an installed local model and context of at least 2048"
            )
        if not 30 <= timeout_seconds <= 3600:
            raise ConfigurationError(
                "ESPERIA_OLLAMA_TIMEOUT_SECONDS must be between 30 and 3600"
            )
        self.timeout_seconds = timeout_seconds
        self.model_name = model
        self.context = context
        self.cache_identity = ""
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                timeout_seconds,
                connect=self.settings.connect_timeout,
                write=self.settings.write_timeout,
                pool=self.settings.pool_timeout,
            ),
            follow_redirects=False,
            trust_env=False,
        )

    def check_login(self) -> None:
        """Verify installed weights, completion support, context capacity, and model digest."""
        try:
            response = self.client.get(
                "/api/tags", timeout=self.settings.metadata_timeout
            )
            response.raise_for_status()
            selected = next(
                (m for m in response.json()["models"] if m["name"] == self.model_name),
                None,
            )
            if selected is None:
                raise ConfigurationError(
                    "ESPERIA_OLLAMA_MODEL is not installed; no download was attempted"
                )
            response = self.client.post(
                "/api/show",
                json={"model": self.model_name},
                timeout=self.settings.metadata_timeout,
            )
            response.raise_for_status()
            info = response.json()
            if any(
                value.get("remote_model") or value.get("remote_host")
                for value in (selected, info)
            ) or not info.get("tensors"):
                raise ConfigurationError(
                    "Ollama backend requires local weights; remote models are disabled"
                )
            if "completion" not in info.get("capabilities", []):
                raise ConfigurationError(
                    "Selected Ollama model does not support text completion"
                )
            capacity = max(
                (
                    int(v)
                    for k, v in info.get("model_info", {}).items()
                    if k.endswith(".context_length")
                ),
                default=0,
            )
            if capacity < self.context:
                raise ConfigurationError(
                    "ESPERIA_OLLAMA_CONTEXT exceeds the model's verified context capacity"
                )
            self.cache_identity = json.dumps(
                [
                    self.base_url,
                    selected["digest"],
                    self.context,
                    self.settings.ollama_temperature,
                ]
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            if isinstance(error, ConfigurationError):
                raise
            raise ConfigurationError(
                "Cannot verify local Ollama. Check that Ollama is running and the selected model is installed"
            ) from None

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        """Generate bounded JSON locally, rejecting incomplete responses at the runner."""
        if not self.cache_identity:
            raise ConfigurationError("Check the Ollama server before starting research")
        try:
            response = self.client.post(
                "/api/chat",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": prompt},
                    ],
                    "format": json.loads(prompt)["output_schema"],
                    "stream": False,
                    "options": {
                        "temperature": self.settings.ollama_temperature,
                        "num_predict": maximum,
                        "num_ctx": self.context,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return Completion(
                data["message"]["content"],
                data.get("prompt_eval_count", 0),
                data.get("eval_count", 0),
                data.get("created_at", "ollama-local"),
                data.get("done") is True and data.get("done_reason") == "stop",
            )
        except httpx.TimeoutException:
            raise ConfigurationError(
                f"Local Ollama timed out (response wait: {self.timeout_seconds}s). Generation may be incomplete; no automatic retry. Increase ESPERIA_OLLAMA_TIMEOUT_SECONDS for slow local models, or reduce the workload. No cloud fallback was attempted"
            ) from None
        except httpx.HTTPStatusError as error:
            raise ConfigurationError(
                f"Local Ollama returned HTTP {error.response.status_code}. Inspect Ollama server logs; no automatic retry or cloud fallback"
            ) from None
        except httpx.TransportError:
            raise ConfigurationError(
                "Connection to local Ollama failed. Check that its server is running; no automatic retry or cloud fallback"
            ) from None
        except (KeyError, TypeError, ValueError):
            raise ConfigurationError(
                "Local Ollama generation failed; check server logs and available memory. No cloud fallback was attempted"
            ) from None

    def close(self) -> None:
        """Release the HTTP connection."""
        self.client.close()
