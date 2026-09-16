"""Shared stage execution, accounting and content-keyed validated result reuse.

Example: runner.invoke("analysis", model, task, OutputSchema)
Cache keys include complete input, instructions, schema, backend/model identity and output bound.
"""

import json
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Protocol, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from esperia.ledger import Ledger
from esperia.provider import Completion, ProviderFailure, cost_cents, reservation_cents
from esperia.subscription import ConfigurationError


class OutputValidationError(ValueError):
    """Safe, application-authored output diagnostics; never include model text."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


class Provider(Protocol):
    """One model completion boundary, without provider-specific orchestration."""

    def complete(
        self, model: str, instructions: str, prompt: str, maximum: int
    ) -> Completion: ...


T = TypeVar("T", bound=BaseModel)


class StageRunner:
    """Execute stages against explicit workers and an optional separate reviewer."""

    def __init__(
        self,
        ledger: Ledger,
        provider: Provider,
        job_id: str,
        output: Path,
        instructions: str,
        progress: Callable[[str], None],
        reviewer: Provider | None = None,
        cache: Path | None = None,
        refresh: bool = False,
    ):
        self.ledger, self.provider, self.job_id = ledger, provider, job_id
        self.output, self.instructions, self.progress = output, instructions, progress
        self.reviewer = reviewer if reviewer is not None else provider
        self.cache, self.refresh = cache, refresh

    def validate_output(
        self,
        stage: str,
        text: str,
        complete: bool,
        schema: type[T],
        validate: Callable[[T], None] | None,
    ) -> T:
        """Persist safe diagnostics for incomplete, malformed or unsupported output."""
        try:
            if not complete:
                raise OutputValidationError(
                    [
                        "Model response incomplete; output limit or interrupted generation"
                    ]
                )
            try:
                parsed = schema.model_validate_json(text)
            except ValidationError:
                raise OutputValidationError(
                    ["Response does not match the required JSON schema"]
                ) from None
            if validate:
                validate(parsed)
            return parsed
        except OutputValidationError as error:
            path = self.output / f"{stage}-validation.json"
            path.write_text(
                json.dumps(
                    {
                        "stage": stage,
                        "code": "invalid_model_output",
                        "issues": error.issues,
                        "response_artifact": f"{stage}.json",
                        "automatic_retry": False,
                    },
                    indent=2,
                )
            )
            raise OutputValidationError(
                [
                    f"{stage} rejected: {'; '.join(error.issues)}. "
                    f"Saved response and diagnostics: {path.resolve()}. No automatic retry."
                ]
            ) from None

    def invoke(
        self,
        stage: str,
        model: str,
        prompt: str,
        schema: type[T],
        maximum: int = 3500,
        validate: Callable[[T], None] | None = None,
    ) -> T:
        ledger, output, progress = self.ledger, self.output, self.progress
        job_id = self.job_id
        provider = self.reviewer if stage.startswith("review") else self.provider
        model = getattr(provider, "model_name", model)
        full_prompt = json.dumps(
            {"task": prompt, "output_schema": schema.model_json_schema()}
        )
        billing = getattr(provider, "billing_mode", "api")
        identity = getattr(provider, "cache_identity", type(provider).__name__)
        cache_key = sha256(
            json.dumps(
                ["economy-v1", self.instructions, full_prompt, model, identity, maximum]
            ).encode()
        ).hexdigest()
        cache_path = self.cache / f"{cache_key}.json" if self.cache else None
        if cache_path and cache_path.exists() and not self.refresh:
            cached = json.loads(cache_path.read_text())
            (output / f"{stage}.json").write_text(
                json.dumps(
                    {
                        **cached,
                        "cache_hit": True,
                        "input_tokens": 0,
                        "output_tokens": 0,
                    },
                    indent=2,
                )
            )
            parsed = self.validate_output(
                stage, cached["text"], cached.get("complete") is True, schema, validate
            )
            progress(f"{stage}: reused validated cached result; no model call")
            return parsed
        subscription = billing in {"subscription", "local"}
        if subscription:
            call_id = ledger.reserve_subscription_call(job_id, stage, model)
            progress(f"{stage}: {model}; {billing}")
        else:
            bound = reservation_cents(model, self.instructions, full_prompt, maximum)
            call_id = ledger.reserve_call(job_id, stage, model, bound)
            progress(f"{stage}: {model}; reserved up to {bound} cents")
        try:
            response = provider.complete(model, self.instructions, full_prompt, maximum)
        except ProviderFailure as error:
            if error.rejected:
                ledger.settle_call(call_id, 0, f"rejected:{error.code}")
            else:
                ledger.uncertain_call(call_id)
            (output / f"{stage}-error.json").write_text(
                json.dumps(
                    {
                        "stage": stage,
                        "status": error.status,
                        "code": error.code,
                        "billing": (
                            "rejected before generation"
                            if error.rejected
                            else "uncertain"
                        ),
                    },
                    indent=2,
                )
            )
            raise
        except ConfigurationError as error:
            ledger.uncertain_call(call_id)
            (output / f"{stage}-error.json").write_text(
                json.dumps(
                    {
                        "stage": stage,
                        "code": "provider_failure",
                        "message": str(error),
                        "outcome": "uncertain",
                        "automatic_retry": False,
                    },
                    indent=2,
                )
            )
            raise
        except Exception:
            ledger.uncertain_call(call_id)
            raise RuntimeError(
                "Provider call failed; billing is uncertain. No automatic retry."
            ) from None
        ledger.settle_call(
            call_id,
            (
                0
                if subscription
                else cost_cents(model, response.input_tokens, response.output_tokens)
            ),
            response.response_id,
        )
        # Save observed output before parsing so a paid response is never lost on validation failure.
        (output / f"{stage}.json").write_text(
            json.dumps(
                {
                    "model": model,
                    "billing_mode": billing,
                    "response_id": response.response_id,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "complete": response.complete,
                    "text": response.text,
                },
                indent=2,
            )
        )
        parsed = self.validate_output(
            stage, response.text, response.complete, schema, validate
        )
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix(f".{uuid4()}.tmp")
            temporary.write_text((output / f"{stage}.json").read_text())
            temporary.replace(cache_path)
        return parsed
