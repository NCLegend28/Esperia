"""Validated owner configuration. Example: settings = load_settings(Path('esperia.json')).

Defaults are centralized here; modules receive a resolved Settings explicitly.
Private credentials are excluded from this serializable configuration.
"""

import json
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Profile(BaseModel):
    """Versioned task template, independent of model/provider and topic."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = "general"
    version: str = "1"
    checks: list[str] = Field(
        default_factory=lambda: [
            "scope",
            "citations",
            "reasoning",
            "counterarguments",
            "uncertainty",
        ]
    )
    instructions: str = (
        "Answer the user's actual question and requested time horizon. State the selected scope, distinguish facts from assumptions, compare relevant evidence, address counterarguments and disclose missing information. Do not substitute unrelated entities or a different topic."
    )
    discovery_terms: list[str] = Field(default_factory=list)
    source_instructions: str = (
        "Search for current primary sources relevant to the actual question. If the scope is broad, choose and disclose a defensible representative comparison; never claim exhaustive coverage. Prefer specific readable reports, disclosures or documentation over homepages. Use only URLs found through web search. Explain why each source belongs in scope."
    )

    @model_validator(mode="after")
    def validate_checks(self) -> Self:
        if (
            not self.checks
            or len(set(self.checks)) != len(self.checks)
            or any(not c.strip() for c in self.checks)
        ):
            raise ValueError("Profile checks must be distinct and nonempty")
        return self


class SearchSettings(BaseModel):
    """Owner-selected search connection and finite discovery budgets."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    endpoint: str | None = None
    max_calls: int = Field(default=3, ge=1, le=12)
    results: int = Field(default=8, ge=1, le=24)
    query_chars: int = Field(default=1000, ge=1, le=4000)
    text_chars: int = Field(default=800, ge=1, le=4000)
    response_bytes: int = Field(default=1000000, ge=100, le=5000000)
    output_bytes: int = Field(default=24000, ge=100, le=100000)
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class LoopSettings(BaseModel):
    """Owner-configured finite investigation limits, separate from tool limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    steps: int = Field(default=10, ge=3, le=64)
    seconds: int = Field(default=1800, ge=1, le=14400)
    repeated_actions: int = Field(default=2, ge=1, le=10)
    read_calls: int = Field(default=4, ge=1, le=24)
    observation_chars: int = Field(default=4000, ge=600, le=12000)


class Settings(BaseModel):
    """Overridable choices with finite safety ceilings and consistent budgets."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    profile: Profile = Field(default_factory=Profile)
    question_assistant_id: str = Field(
        default="research-guide", min_length=1, max_length=200
    )
    question_turn_limit: int = Field(default=8, ge=1, le=16)
    question_brief_tokens: int = Field(default=1800, ge=256, le=8000)
    question_instructions: str = Field(
        default=(
            "Help the owner formulate an answerable research question. Preserve their intent and distinguish their constraints from suggested assumptions. "
            "Clarify the decision, audience, key terms, comparison, geography and time horizon only when material. "
            "Ask a small prioritized set of clarifying questions; do not invent answers on the owner's behalf. "
            "Propose evidence requirements, counterevidence and falsifiable success criteria. Accuracy is mandatory: identify factual premises requiring verification. "
            "This is question preparation, not research: do not assert empirical findings, invent sources, browse or execute research."
        ),
        min_length=1,
        max_length=12000,
    )
    notebook_page_size: int = Field(default=100, ge=1, le=1000)
    notebook_edge_limit: int = Field(default=1000, ge=1, le=10000)
    notebook_input_bytes: int = Field(default=1000000, ge=1000, le=10000000)
    data_root: Path = Path(".local/dev")
    database: Path | None = None
    backend: Literal["codex", "llama", "hybrid", "ollama", "ollama-hybrid"] = "codex"
    repair_backend: Literal["codex", "llama", "hybrid", "ollama", "ollama-hybrid"] = (
        "ollama"
    )
    mode: Literal["economy", "deep"] = "economy"
    planner_model: str = "gpt-6-astra"
    analyst_model: str = "gpt-5.6-terra"
    reviewer_model: str = "gpt-6-astra"
    source_model: str = "gpt-5.6-terra"
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "low"
    source_search: Literal["codex", "explicit", "tools"] = "codex"
    search: SearchSettings = Field(default_factory=SearchSettings)
    agent: LoopSettings = Field(default_factory=LoopSettings)
    allowed_hosts: list[str] = Field(default_factory=list)
    monthly_cents: int = Field(default=6500, ge=0)
    job_cents: int = Field(default=500, gt=0)
    max_calls: int = Field(default=32, ge=1, le=128)
    revision_rounds: int = Field(default=2, ge=0, le=10)
    economy_revision: bool = True
    repair_calls: int = Field(default=2, ge=2, le=128)
    question_chars: int = Field(default=4000, ge=1, le=24000)
    max_seeds: int = Field(default=12, ge=1, le=24)
    documents: int = Field(default=18, ge=1, le=24)
    requests: int = Field(default=36, ge=1, le=128)
    depth: int = Field(default=2, ge=0, le=5)
    links_per_page: int = Field(default=2000, ge=1, le=10000)
    followed_links: int = Field(default=8, ge=1, le=100)
    link_context_chars: int = Field(default=3000, ge=1, le=12000)
    query_term_min: int = Field(default=2, ge=1, le=20)
    query_stopwords: list[str] = Field(
        default_factory=lambda: [
            "the",
            "and",
            "for",
            "with",
            "over",
            "next",
            "their",
            "compare",
            "potential",
            "what",
            "which",
            "how",
            "are",
            "does",
            "from",
            "into",
        ]
    )
    query_weight: int = Field(default=4, ge=1)
    profile_weight: int = Field(default=1, ge=0)
    pdf_weight: int = Field(default=0, ge=0)
    recency_weight: int = Field(default=1, ge=0)
    excluded_link_terms: list[str] = Field(
        default_factory=lambda: [".zip", "webcast", "login", "privacy", "unsubscribe"]
    )
    html_bytes: int = Field(default=2000000, ge=100, le=25000000)
    document_bytes: int = Field(default=25000000, ge=100, le=50000000)
    extracted_chars: int = Field(default=2000000, ge=100, le=5000000)
    minimum_text: int = Field(default=100, ge=20, le=1000)
    source_chars: int = Field(default=12000, ge=600, le=12000)
    evidence_chars: int = Field(default=60000, ge=12000, le=180000)
    passage_chars: int = Field(default=900, ge=100, le=2000)
    excerpt_chars: int = Field(default=500, ge=20, le=600)
    excerpt_stride: int = Field(default=400, ge=1, le=600)
    archive_hours: int = Field(default=48, ge=1, le=720)
    collect_retries: int = Field(default=1, ge=0, le=3)
    http_timeout: int = Field(default=30, ge=1, le=300)
    pdf_timeout: int = Field(default=45, ge=1, le=300)
    pdf_pages: int = Field(default=300, ge=1, le=1000)
    pdf_stream_bytes: int = Field(default=20000000, ge=100, le=50000000)
    codex_timeout: int = Field(default=240, ge=30, le=3600)
    metadata_timeout: int = Field(default=10, ge=1, le=60)
    login_timeout: int = Field(default=20, ge=1, le=120)
    prompt_bytes: int = Field(default=180000, ge=1000, le=500000)
    plan_tokens: int = Field(default=2000, ge=100, le=8000)
    analysis_tokens: int = Field(default=5000, ge=100, le=8000)
    notes_tokens: int = Field(default=3500, ge=100, le=8000)
    draft_tokens: int = Field(default=6000, ge=100, le=8000)
    review_tokens: int = Field(default=3500, ge=100, le=8000)
    source_tokens: int = Field(default=2500, ge=100, le=8000)
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_context: int = Field(default=32768, ge=2048)
    ollama_timeout: int = Field(default=900, ge=30, le=3600)
    ollama_temperature: float = Field(default=0, ge=0, le=2)
    llama_url: str = "http://127.0.0.1:8080"
    llama_model: str | None = None
    llama_timeout: int = Field(default=240, ge=30, le=3600)
    llama_temperature: float = Field(default=0.1, ge=0, le=2)
    connect_timeout: int = Field(default=10, ge=1, le=120)
    write_timeout: int = Field(default=30, ge=1, le=300)
    pool_timeout: int = Field(default=10, ge=1, le=120)
    sqlite_timeout: int = Field(default=10, ge=1, le=120)
    repair_tasks: int = Field(default=64, ge=1, le=128)
    repair_chars: int = Field(default=24000, ge=100, le=100000)
    title_chars: int = Field(default=240, ge=1, le=1000)
    reason_chars: int = Field(default=2000, ge=1, le=24000)
    api_timeout: int = Field(default=180, ge=1, le=3600)
    api_framing_tokens: int = Field(default=4096, ge=0)
    api_rates: dict[str, tuple[int, int]] = Field(
        default_factory=lambda: {
            "gpt-5.6-terra": (200, 900),
            "gpt-6-astra": (1000, 3750),
        }
    )

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (
            self.requests < self.documents
            or self.evidence_chars // self.documents < self.passage_chars
        ):
            raise ValueError(
                "Request/evidence budgets must support the document budget"
            )
        if (
            self.excerpt_stride > self.excerpt_chars
            or self.repair_calls > self.max_calls
        ):
            raise ValueError("Inconsistent excerpt stride or repair call budget")
        if any(min(rate) < 0 for rate in self.api_rates.values()):
            raise ValueError("API rates cannot be negative")
        if any(
            not model.strip()
            for model in (
                self.planner_model,
                self.analyst_model,
                self.reviewer_model,
                self.source_model,
            )
        ):
            raise ValueError("Model choices must be nonempty")
        return self

    @property
    def source_call_budget(self) -> int:
        """Reserve one model decision per tool call plus a final source selection."""
        return self.search.max_calls + 1 if self.source_search == "tools" else 1

    @property
    def research_root(self) -> Path:
        """Directory containing jobs and the shared validated cache."""
        return self.data_root / "research"

    def call_budget(
        self, mode: str, resolve_sources: bool = False, source_count: int | None = None
    ) -> int:
        """Derive the workflow budget; never change an explicit owner cap."""
        stages = (
            2 + int(self.economy_revision)
            if mode == "economy"
            else (self.documents if source_count is None else source_count)
            + 3
            + 2 * self.revision_rounds
        )
        return min(
            self.max_calls, stages + (self.source_call_budget if resolve_sources else 0)
        )


def load_settings(path: Path | None = None, workspace: Path | None = None) -> Settings:
    """Load JSON overrides; resolve paths relative to the selected workspace.

    Example: load_settings(Path('/work/esperia.json'), Path('/work'))
    """
    base = (workspace or (path.resolve().parent if path else Path.cwd())).resolve()
    settings = Settings.model_validate_json(path.read_text()) if path else Settings()
    updates: dict[str, object] = {"data_root": (base / settings.data_root).resolve()}
    if settings.database is not None:
        updates["database"] = (base / settings.database).resolve()
    return Settings.model_validate({**settings.model_dump(), **updates})


def save_settings(settings: Settings, output: Path) -> None:
    """Persist public configuration for reproducibility; no credentials are included."""
    output.mkdir(parents=True, exist_ok=True)
    (output / "resolved-config.json").write_text(
        json.dumps(settings.model_dump(mode="json"), indent=2)
    )
