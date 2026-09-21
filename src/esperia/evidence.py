"""Bounded HTTPS collection from owner-approved public domains.

Example: collect(["https://investors.ionq.com/financials/quarterly-results/"], Path("archive"))
Raw snapshots are content-addressed. HTML is data, never executable instructions.
"""

import json
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, TypeAdapter

from esperia.network import PublicTransport, validate_public_url
from esperia.settings import Settings


class Source(BaseModel):
    """Dated extracted evidence linked to the complete downloaded snapshot."""

    id: str = Field(pattern=r"^S[1-9][0-9]?$")
    url: str
    fetched_at: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str = Field(max_length=12000)
    content_type: str = "text/html"
    truncated: bool
    extraction_version: int = 1
    projection_chars: int | None = Field(default=None, ge=1, le=12000)
    passages: list[tuple[int, int]] = Field(default_factory=list)
    extracted_sha256: str | None = None
    discovered_from: str | None = None


class TextExtractor(HTMLParser):
    """Extract visible text while dropping scripts, styles and navigation."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def validate_url(url: str, settings: Settings | None = None) -> None:
    """Validate public HTTPS syntax and an optional explicit owner host policy."""
    validate_public_url(url, settings or Settings())


def _collect_once(urls: list[str], output: Path, settings: Settings) -> list[Source]:
    """Fetch bounded public HTML/text sources without redirects or proxy inheritance.

    A failed source aborts collection. Partial snapshots remain available but are
    never silently substituted for a complete manifest. PDFs require a later adapter.
    """
    if not 1 <= len(urls) <= settings.max_seeds or len(set(urls)) != len(urls):
        raise ValueError(f"Provide 1–{settings.max_seeds} distinct source URLs")
    for url in urls:
        validate_url(url, settings)
    output.mkdir(parents=True, exist_ok=True)
    sources: list[Source] = []
    with httpx.Client(
        timeout=settings.http_timeout,
        transport=PublicTransport(settings),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for index, url in enumerate(urls, 1):
            print(f"Collecting S{index}: {url}", flush=True)
            with client.stream("GET", url) as response:
                response.raise_for_status()
                kind = response.headers.get("content-type", "").split(";")[0]
                if kind not in {"text/html", "text/plain", "application/xhtml+xml"}:
                    raise ValueError(
                        "Unsupported evidence type; expected HTML or plain text"
                    )
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > settings.html_bytes:
                        raise ValueError(
                            f"Source exceeds the {settings.html_bytes}-byte download limit"
                        )
            digest = sha256(body).hexdigest()
            snapshot = output / f"{digest}.source"
            if not snapshot.exists():
                with snapshot.open("xb") as stream:
                    stream.write(body)
            elif sha256(snapshot.read_bytes()).hexdigest() != digest:
                raise ValueError(
                    "Existing source archive failed integrity verification"
                )
            decoded = body.decode("utf-8", errors="replace")
            parser = TextExtractor()
            parser.feed(decoded)
            text = " ".join(parser.parts) if kind != "text/plain" else decoded
            if len(text) < settings.minimum_text:
                raise ValueError("Source contains insufficient readable text")
            sources.append(
                Source(
                    id=f"S{index}",
                    content_type=kind,
                    url=url,
                    fetched_at=datetime.now(UTC).isoformat(),
                    sha256=digest,
                    text=text[: settings.source_chars],
                    projection_chars=settings.source_chars,
                    truncated=len(text) > settings.source_chars,
                )
            )
            (output / f"S{index}.json").write_text(
                sources[-1].model_dump_json(indent=2)
            )
    (output / "sources.json").write_text(
        json.dumps([source.model_dump() for source in sources], indent=2)
    )
    return sources


def collect(
    urls: list[str], output: Path, settings: Settings | None = None
) -> list[Source]:
    """Retry idempotent source collection within the configured timeout-retry budget.

    Completed snapshots and individual source metadata survive partial failures.
    Access denials and validation errors are never retried or bypassed.
    """
    settings = settings or Settings()
    for attempt in range(settings.collect_retries + 1):
        try:
            return _collect_once(urls, output, settings)
        except httpx.TimeoutException:
            if attempt == settings.collect_retries:
                raise
            print(
                "Public-source timeout; retrying within the configured collection budget. No model call was made.",
                flush=True,
            )
    raise AssertionError("Unreachable")


def load_archive(path: Path, settings: Settings | None = None) -> list[Source]:
    """Reuse snapshots within the configured freshness window after integrity checks.

    Example: sources = load_archive(Path(".local/dev/research/JOB/evidence"))
    This avoids refetching evidence when fixing configuration or provider access.
    """
    settings = settings or Settings()
    sources = TypeAdapter(list[Source]).validate_json(
        (path / "sources.json").read_text()
    )
    if not 1 <= len(sources) <= 24 or len({s.id for s in sources}) != len(sources):
        raise ValueError("Invalid archive source identities")
    for source in sources:
        validate_url(source.url, settings)
        fetched = datetime.fromisoformat(source.fetched_at)
        if fetched.tzinfo is None:
            raise ValueError("Archive dates must include a timezone")
        age = (datetime.now(UTC) - fetched).total_seconds()
        if not 0 <= age <= settings.archive_hours * 3600:
            raise ValueError("Archive is stale or future-dated; collect fresh evidence")
        raw = (path / f"{source.sha256}.source").read_bytes()
        if sha256(raw).hexdigest() != source.sha256:
            raise ValueError("Archive content hash mismatch")
        if source.extraction_version == 2:
            from esperia.discovery import extract_document, projected_text

            text = extract_document(
                raw, source.content_type, path / f"{source.sha256}.source", settings
            )
            if sha256(text.encode()).hexdigest() != source.extracted_sha256:
                raise ValueError("Extracted document hash mismatch")
            if (
                not source.passages
                or any(not 0 <= a < b <= len(text) for a, b in source.passages)
                or source.passages != sorted(source.passages)
                or any(
                    a[1] > b[0] for a, b in zip(source.passages, source.passages[1:])
                )
            ):
                raise ValueError("Invalid source passage offsets")
            if projected_text(
                text, source.passages
            ) != source.text or source.truncated != (
                len(text) > sum(b - a for a, b in source.passages)
            ):
                raise ValueError("Archive selected passages were modified")
            continue
        if source.extraction_version != 1:
            raise ValueError("Unknown extraction version")
        decoded = raw.decode("utf-8", errors="replace")
        parser = TextExtractor()
        parser.feed(decoded)
        text = (
            decoded if source.content_type == "text/plain" else " ".join(parser.parts)
        )
        # Legacy v1 archives used a 12,000-character projection.
        projection = source.projection_chars or 12000
        if text[:projection] != source.text or source.truncated != (
            len(text) > projection
        ):
            raise ValueError("Archive extracted text was modified")
    return sources
