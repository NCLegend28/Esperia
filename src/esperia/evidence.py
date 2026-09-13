"""Bounded HTTPS collection from owner-approved public domains.

Example: collect(["https://investors.ionq.com/financials/quarterly-results/"], Path("archive"))
Raw snapshots are content-addressed. HTML is data, never executable instructions.
"""

import json
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, TypeAdapter

ALLOWED_HOSTS = frozenset(
    {
        "investors.ionq.com",
        "www.ionq.com",
        "investors.rigetti.com",
        "ir.infleqtion.com",
        "investors.xanadu.ai",
        "ir.arqit.uk",
        "www.sealsq.com",
        "www.sec.gov",
    }
)
MAX_BYTES = 2_000_000


class Source(BaseModel):
    """Dated extracted evidence linked to the complete downloaded snapshot."""

    id: str = Field(pattern=r"^S[1-9][0-9]?$")
    url: str
    fetched_at: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str = Field(max_length=12000)
    content_type: str = "text/html"
    truncated: bool


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


def validate_url(url: str) -> None:
    """Reject unapproved hosts, credentials, non-HTTPS URLs and custom ports."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or parsed.fragment
    ):
        raise ValueError("Source URL is outside the approved HTTPS domain policy")


def _collect_once(urls: list[str], output: Path) -> list[Source]:
    """Fetch 1–12 approved HTML/text sources without redirects or proxy inheritance.

    A failed source aborts collection. Partial snapshots remain available but are
    never silently substituted for a complete manifest. PDFs require a later adapter.
    """
    if not 1 <= len(urls) <= 12 or len(set(urls)) != len(urls):
        raise ValueError("Provide 1–12 distinct source URLs")
    for url in urls:
        validate_url(url)
    output.mkdir(parents=True, exist_ok=True)
    sources: list[Source] = []
    with httpx.Client(
        timeout=30,
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
                    if len(body) > MAX_BYTES:
                        raise ValueError("Source exceeds the 2 MB download limit")
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
            if len(text) < 100:
                raise ValueError("Source contains insufficient readable text")
            sources.append(
                Source(
                    id=f"S{index}",
                    content_type=kind,
                    url=url,
                    fetched_at=datetime.now(UTC).isoformat(),
                    sha256=digest,
                    text=text[:12000],
                    truncated=len(text) > 12000,
                )
            )
            (output / f"S{index}.json").write_text(
                sources[-1].model_dump_json(indent=2)
            )
    (output / "sources.json").write_text(
        json.dumps([source.model_dump() for source in sources], indent=2)
    )
    return sources


def collect(urls: list[str], output: Path) -> list[Source]:
    """Retry an idempotent public-source collection once on a transport timeout.

    Completed snapshots and individual source metadata survive partial failures.
    Access denials and validation errors are never retried or bypassed.
    """
    for attempt in range(2):
        try:
            return _collect_once(urls, output)
        except httpx.TimeoutException:
            if attempt:
                raise
            print(
                "Public-source timeout; retrying collection once. No model call was made.",
                flush=True,
            )
    raise AssertionError("Unreachable")


def load_archive(path: Path) -> list[Source]:
    """Reuse at most 48-hour-old snapshots after hash and extracted-text checks.

    Example: sources = load_archive(Path(".local/dev/research/JOB/evidence"))
    This avoids refetching evidence when fixing configuration or provider access.
    """
    sources = TypeAdapter(list[Source]).validate_json(
        (path / "sources.json").read_text()
    )
    if not 1 <= len(sources) <= 12 or len({s.id for s in sources}) != len(sources):
        raise ValueError("Invalid archive source identities")
    for source in sources:
        validate_url(source.url)
        fetched = datetime.fromisoformat(source.fetched_at)
        if fetched.tzinfo is None:
            raise ValueError("Archive dates must include a timezone")
        age = (datetime.now(UTC) - fetched).total_seconds()
        if not 0 <= age <= 172800:
            raise ValueError("Archive is stale or future-dated; collect fresh evidence")
        raw = (path / f"{source.sha256}.source").read_bytes()
        if sha256(raw).hexdigest() != source.sha256:
            raise ValueError("Archive content hash mismatch")
        decoded = raw.decode("utf-8", errors="replace")
        parser = TextExtractor()
        parser.feed(decoded)
        text = (
            decoded if source.content_type == "text/plain" else " ".join(parser.parts)
        )
        if text[:12000] != source.text or source.truncated != (len(text) > 12000):
            raise ValueError("Archive extracted text was modified")
    return sources
