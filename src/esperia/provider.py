"""Explicit OpenAI adapter with no tools, retries or secret logging.

Example: provider = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"])
Only approved text is sent. Transport failures are treated as uncertain billing.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from openai import APIStatusError, DefaultHttpxClient, OpenAI

from esperia.settings import Settings

# Conservative standard-processing LONG-context rates, checked 2026-09-13.
# Source: https://developers.openai.com/api/docs/pricing
# Units: USD cents per million tokens. No cache discount is assumed.
RATES = Settings().api_rates


def cost_cents(
    model: str, input_tokens: int, output_tokens: int, settings: Settings | None = None
) -> int:
    """Conservatively account token usage; not a provider invoice reconciliation."""
    rates = (settings or Settings()).api_rates
    if model not in rates or min(input_tokens, output_tokens) < 0:
        raise ValueError("Unknown model or invalid usage")
    incoming, outgoing = rates[model]
    amount = Decimal(input_tokens * incoming + output_tokens * outgoing) / 1_000_000
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def reservation_cents(
    model: str,
    instructions: str,
    prompt: str,
    maximum: int,
    settings: Settings | None = None,
) -> int:
    """Reserve using UTF-8 byte count plus framing allowance as a token bound."""
    settings = settings or Settings()
    if len(prompt.encode()) > settings.prompt_bytes or not 1 <= maximum <= 8000:
        raise ValueError("Request exceeds the bounded research context/output policy")
    return max(
        1,
        cost_cents(
            model,
            len((instructions + prompt).encode()) + settings.api_framing_tokens,
            maximum,
            settings,
        ),
    )


@dataclass(frozen=True)
class Completion:
    """Provider result and observed usage, including incomplete responses."""

    text: str
    input_tokens: int
    output_tokens: int
    response_id: str
    complete: bool


class ProviderFailure(RuntimeError):
    """Sanitized failure metadata safe for the local activity record."""

    def __init__(self, status: int, code: str, rejected: bool):
        super().__init__(f"OpenAI rejected or failed the call: HTTP {status}, {code}")
        self.status = status
        self.code = code
        self.rejected = rejected


class OpenAIProvider:
    """Use the official endpoint with explicit credentials and zero automatic retries."""

    def __init__(self, api_key: str, settings: Settings | None = None):
        self.settings = settings or Settings()
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is not configured")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            max_retries=0,
            timeout=self.settings.api_timeout,
            http_client=DefaultHttpxClient(
                trust_env=False, timeout=self.settings.api_timeout
            ),
        )

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion:
        """Perform one bounded text call. Caller reserves before invoking this method."""
        if model not in self.settings.api_rates:
            raise ValueError("Model has no reviewed rate configuration")
        try:
            response = self.client.responses.create(
                model=model,
                instructions=instructions,
                input=prompt,
                max_output_tokens=maximum,
                store=False,
                service_tier="default",
                reasoning={"effort": self.settings.reasoning_effort},
            )
        except APIStatusError as error:
            known = {
                "credit_balance_exhausted",
                "insufficient_quota",
                "invalid_api_key",
                "model_not_found",
            }
            code = (
                error.code
                if isinstance(error.code, str) and error.code in known
                else "provider_error"
            )
            rejected = code in known and error.status_code in {400, 401, 403, 404, 429}
            raise ProviderFailure(error.status_code, code, rejected) from None
        if response.usage is None:
            raise ValueError("Provider returned no usage; reconcile before retrying")
        return Completion(
            response.output_text,
            response.usage.input_tokens,
            response.usage.output_tokens,
            response.id,
            response.status == "completed",
        )

    def close(self) -> None:
        """Release HTTP resources."""
        self.client.close()
