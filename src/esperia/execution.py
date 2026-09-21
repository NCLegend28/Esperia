"""Shared stage execution, accounting and content-keyed validated result reuse.

Example: runner.invoke("analysis", model, task, OutputSchema)
Cache keys include complete input, instructions, schema, backend/model identity and output bound.
"""

import json
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from esperia.ledger import Ledger
from esperia.provider import Completion, ProviderFailure, cost_cents, reservation_cents
from esperia.settings import Settings
from esperia.subscription import ConfigurationError


class OutputValidationError(ValueError):
    """Safe, application-authored output diagnostics; never include model text."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def schema_issues(error: ValidationError, schema: type[BaseModel]) -> list[str]:
    """Explain schema failures without exposing response text or arbitrary keys.

    Paths only name fields declared by application-owned schemas; input values,
    custom validator messages and unknown object keys never enter diagnostics.
    """
    fields: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                fields.update(properties)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema.model_json_schema())
    issues: list[str] = []
    for detail in error.errors(
        include_input=False, include_context=False, include_url=False
    ):
        path = (
            ".".join(
                str(part) if isinstance(part, int) or part in fields else "<field>"
                for part in detail["loc"]
            )
            or "<response>"
        )
        issue = f"Response does not match the required JSON schema: {path} ({detail['type']})"
        if issue not in issues:
            issues.append(issue)
    return issues


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
        settings: Settings | None = None,
        before_call: Callable[[], None] | None = None,
        reuse_completed: bool = False,
    ):
        self.before_call, self.reuse_completed = before_call, reuse_completed
        self.settings = settings or ledger.settings
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
            except ValidationError as error:
                raise OutputValidationError(schema_issues(error, schema)) from None
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
        maximum: int | None = None,
        validate: Callable[[T], None] | None = None,
        role: str = "worker",
    ) -> T:
        if self.before_call:
            self.before_call()
        maximum = self.settings.notes_tokens if maximum is None else maximum
        ledger, output, progress = self.ledger, self.output, self.progress
        job_id = self.job_id
        provider = self.reviewer if role == "reviewer" else self.provider
        model = getattr(provider, "model_name", model)
        full_prompt = json.dumps(
            {"task": prompt, "output_schema": schema.model_json_schema()}
        )
        if len(full_prompt.encode()) > self.settings.prompt_bytes:
            issues = [
                "Stage prompt exceeds the configured byte budget; reduce evidence or output context"
            ]
            (output / f"{stage}-validation.json").write_text(
                json.dumps({"stage": stage, "issues": issues, "automatic_retry": False})
            )
            raise OutputValidationError(issues)
        billing = getattr(provider, "billing_mode", "api")
        identity = getattr(provider, "cache_identity", type(provider).__name__)
        cache_key = sha256(
            json.dumps(
                [
                    "stages-v2",
                    self.settings.model_dump(mode="json"),
                    self.instructions,
                    full_prompt,
                    model,
                    identity,
                    maximum,
                    role,
                ]
            ).encode()
        ).hexdigest()
        saved_path = output / f"{stage}.json"
        if self.reuse_completed and saved_path.is_file():
            saved = json.loads(saved_path.read_text())
            calls = [
                call for call in ledger.list_calls(job_id) if call["stage"] == stage
            ]
            if (
                saved.get("input_sha256") != cache_key
                or any(call["state"] != "settled" for call in calls)
                or (not calls and not saved.get("cache_hit"))
            ):
                raise OutputValidationError(
                    [
                        "Saved stage does not match this execution or has an unresolved call; no replay"
                    ]
                )
            parsed = self.validate_output(
                stage, saved["text"], saved.get("complete") is True, schema, validate
            )
            progress(f"{stage}: restored completed checkpoint; no model call")
            return parsed
        cache_path = self.cache / f"{cache_key}.json" if self.cache else None
        if cache_path and cache_path.exists() and not self.refresh:
            cached = json.loads(cache_path.read_text())
            (output / f"{stage}.json").write_text(
                json.dumps(
                    {
                        **cached,
                        "input_sha256": cache_key,
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
            bound = reservation_cents(
                model, self.instructions, full_prompt, maximum, self.settings
            )
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
                else cost_cents(
                    model, response.input_tokens, response.output_tokens, self.settings
                )
            ),
            response.response_id,
        )
        # Save observed output before parsing so a paid response is never lost on validation failure.
        (output / f"{stage}.json").write_text(
            json.dumps(
                {
                    "model": model,
                    "input_sha256": cache_key,
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
