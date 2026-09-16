"""Bounded issuer-link discovery, filing extraction and query-focused evidence.

Example: discover(seeds, "cash flow dilution risks", Path("evidence"))
No LLM/search credits are used. This is an audited link crawl, not open-web search.
"""

import json
import re
import subprocess
import sys
from collections import deque
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin

import httpx

from esperia.evidence import Source, TextExtractor, validate_url

BREAK = "\n[EXCERPT BREAK]\n"
TERMS = (
    "annual",
    "20-f",
    "10-k",
    "10-q",
    "6-k",
    "financial",
    "earnings",
    "cash flow",
    "balance sheet",
    "risk factors",
    "dilution",
    "warrants",
    "shares outstanding",
    "revenue",
    "debt",
    "loss",
    "liquidity",
)


class DiscoveryFailure(ValueError):
    """Safe collection failure pointing to its persisted coverage record."""


class Links(HTMLParser):
    """Read anchor labels and URLs as untrusted data."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.label: list[str] = []
        self.row_start: int | None = None
        self.row_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.row_start = len(self.links)
            self.row_text = []
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_data(self, data: str) -> None:
        if self.href:
            self.label.append(data)
        if self.row_start is not None:
            self.row_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.row_start is not None:
            context = " ".join(self.row_text)[:3000]
            for i in range(self.row_start, len(self.links)):
                href, label = self.links[i]
                self.links[i] = (href, label + " " + context)
            self.row_start = None
        if tag == "a" and self.href:
            self.links.append((self.href, " ".join(self.label)))
            self.href = None


def link_score(url: str, label: str, query: str) -> int:
    """Prioritize filings and financial documents, with a modest recency preference."""
    text = (url + " " + label).lower()
    if any(t in text for t in (".zip", "webcast", "login", "privacy", "unsubscribe")):
        return 0
    if ("sort=" in url or "order=" in url) and "page=" not in url:
        return 0
    if any(t in text for t in ("exx31", "exx32", "ex-31", "ex-32")):
        return 0
    score = sum(3 for term in TERMS if term in text)
    score += (
        6 if any(t in text for t in ("20-f", "10-k", "10-q", "annual-report")) else 0
    )
    score += 4 if ".pdf" in text else 0
    score += sum(
        1 for term in set(re.findall(r"[a-z]{5,}", query.lower())) if term in text
    )
    if score:
        score += 2 if str(datetime.now(UTC).year) in text else 0
    return score


def extract_document(raw: bytes, kind: str, snapshot: Path) -> str:
    """Extract a fetched document; PDF work is isolated with a 45-second timeout."""
    if kind == "application/pdf":
        try:
            response = subprocess.run(
                [sys.executable, "-m", "esperia.pdftext", str(snapshot)],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            if response.returncode:
                message = json.loads(response.stdout).get(
                    "error", "PDF extraction failed"
                )
                raise ValueError(message)
            return str(json.loads(response.stdout)["text"])
        except (subprocess.TimeoutExpired, KeyError, json.JSONDecodeError):
            raise ValueError("PDF extraction exceeded limits or failed") from None
    decoded = raw.decode("utf-8", errors="replace")
    if kind == "text/plain":
        return decoded
    parser = TextExtractor()
    parser.feed(decoded)
    return " ".join(parser.parts)


def select_passages(text: str, query: str, budget: int) -> list[tuple[int, int]]:
    """Select document-wide passages, including identity/context and diverse financial terms."""
    if len(text) <= budget:
        return [(0, len(text))]
    windows = [(i, min(i + 900, len(text))) for i in range(0, len(text), 900)]
    terms = list(TERMS) + list(set(re.findall(r"[a-z]{5,}", query.lower())))
    selected = [windows[0]]
    remaining = windows[1:]
    covered: set[str] = set()
    while (
        remaining and len(selected) * 900 + len(selected) * len(BREAK) + 900 <= budget
    ):

        def score(window: tuple[int, int]) -> int:
            piece = text[window[0] : window[1]].lower()
            return sum((1 if term in covered else 4) for term in terms if term in piece)

        best = max(remaining, key=score)
        if score(best) == 0:
            break
        selected.append(best)
        remaining.remove(best)
        covered.update(t for t in terms if t in text[best[0] : best[1]].lower())
    return sorted(selected)


def projected_text(text: str, ranges: list[tuple[int, int]]) -> str:
    """Project exact ranges with explicit omission markers."""
    return BREAK.join(text[start:end] for start, end in ranges)


def discover(
    seeds: list[str],
    query: str,
    output: Path,
    max_documents: int = 18,
    max_requests: int = 36,
    client: httpx.Client | None = None,
) -> list[Source]:
    """Round-robin crawl up to depth two; failures and out-of-policy links are recorded."""
    if (
        not 1 <= len(seeds) <= 12
        or len(set(seeds)) != len(seeds)
        or not len(seeds) <= max_documents <= 24
        or not max_documents <= max_requests <= 48
    ):
        raise ValueError("Invalid bounded discovery limits or seed list")
    for url in seeds:
        validate_url(url)
    output.mkdir(parents=True, exist_ok=True)
    owned = client is None
    http = client or httpx.Client(timeout=20, follow_redirects=False, trust_env=False)
    queues: list[deque[tuple[str, int, str | None]]] = [
        deque([(url, 0, None)]) for url in seeds
    ]
    visited: set[str] = set()
    documents: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    requests = 0
    try:
        while (
            any(queues) and len(documents) < max_documents and requests < max_requests
        ):
            for seed, queue in zip(seeds, queues):
                if (
                    not queue
                    or len(documents) >= max_documents
                    or requests >= max_requests
                ):
                    continue
                url, depth, parent = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)
                requests += 1
                print(f"Discovering ({requests}/{max_requests}): {url}", flush=True)
                try:
                    with http.stream("GET", url) as response:
                        # Redirect targets must be separately approved and count as requests.
                        if response.is_redirect:
                            target = urldefrag(
                                urljoin(url, response.headers.get("location", ""))
                            )[0]
                            validate_url(target)
                            if depth < 2:
                                queue.appendleft((target, depth + 1, url))
                            events.append(
                                {"url": url, "status": "redirect", "target": target}
                            )
                            continue
                        response.raise_for_status()
                        kind = (
                            response.headers.get("content-type", "")
                            .split(";")[0]
                            .lower()
                        )
                        raw = bytearray()
                        for part in response.iter_bytes():
                            raw.extend(part)
                            if len(raw) > 25_000_000:
                                raise ValueError("Document exceeds 25 MB")
                    if bytes(raw[:5]) == b"%PDF-":
                        kind = "application/pdf"
                    if kind not in {
                        "application/pdf",
                        "text/html",
                        "text/plain",
                        "application/xhtml+xml",
                    }:
                        raise ValueError("Unsupported document type")
                    digest = sha256(raw).hexdigest()
                    snapshot = output / f"{digest}.source"
                    snapshot.write_bytes(raw)
                    text = extract_document(bytes(raw), kind, snapshot)
                    if not 100 <= len(text) <= 2_000_000:
                        raise ValueError("Insufficient or excessive extracted text")
                    (output / f"{digest}.txt").write_text(text)
                    documents.append(
                        {
                            "url": url,
                            "kind": kind,
                            "text": text,
                            "hash": digest,
                            "parent": parent,
                            "seed": seed,
                        }
                    )
                    events.append(
                        {
                            "url": url,
                            "status": "collected",
                            "parent": parent,
                            "depth": depth,
                            "content_type": kind,
                            "sha256": digest,
                        }
                    )
                    if depth < 2 and kind in {"text/html", "application/xhtml+xml"}:
                        parser = Links()
                        parser.feed(bytes(raw).decode("utf-8", errors="replace"))
                        candidates: dict[str, int] = {}
                        for href, label in parser.links[:2000]:
                            link = urldefrag(urljoin(url, href))[0]
                            score = link_score(link, label, query)
                            if not score or link in visited:
                                continue
                            try:
                                validate_url(link)
                            except ValueError:
                                events.append(
                                    {
                                        "url": link[:2000],
                                        "status": "outside_policy",
                                        "parent": url,
                                    }
                                )
                                continue
                            candidates[link] = max(score, candidates.get(link, 0))
                        ranked = sorted(candidates, key=lambda key: -candidates[key])[
                            :8
                        ]
                        for link in reversed(ranked):
                            queue.appendleft((link, depth + 1, url))
                except (httpx.HTTPError, ValueError) as error:
                    events.append(
                        {
                            "url": url,
                            "status": "failed",
                            "reason": (
                                f"HTTP {error.response.status_code}"
                                if isinstance(error, httpx.HTTPStatusError)
                                else (
                                    str(error)
                                    if isinstance(error, ValueError)
                                    else type(error).__name__
                                )
                            ),
                        }
                    )
                (output / "discovery.json").write_text(
                    json.dumps(
                        {
                            "query": query,
                            "seeds": seeds,
                            "events": events,
                            "requests": requests,
                            "documents": len(documents),
                            "seed_coverage": {
                                seed_url: sum(
                                    d.get("seed") == seed_url for d in documents
                                )
                                for seed_url in seeds
                            },
                            "limits": {
                                "documents": max_documents,
                                "requests": max_requests,
                                "depth": 2,
                            },
                        },
                        indent=2,
                    )
                )
    finally:
        if owned:
            http.close()
    (output / "discovery.json").write_text(
        json.dumps(
            {
                "query": query,
                "seeds": seeds,
                "events": events,
                "requests": requests,
                "documents": len(documents),
                "seed_coverage": {
                    seed_url: sum(d.get("seed") == seed_url for d in documents)
                    for seed_url in seeds
                },
                "limits": {
                    "documents": max_documents,
                    "requests": max_requests,
                    "depth": 2,
                },
            },
            indent=2,
        )
    )
    if not documents:
        raise DiscoveryFailure(
            f"Discovery collected no readable documents. Coverage details: {(output / 'discovery.json').resolve()}"
        )
    budget = min(12000, 60000 // len(documents))
    sources: list[Source] = []
    for index, doc in enumerate(documents, 1):
        ranges = select_passages(doc["text"], query, budget)
        source = Source(
            id=f"S{index}",
            url=doc["url"],
            fetched_at=datetime.now(UTC).isoformat(),
            sha256=doc["hash"],
            text=projected_text(doc["text"], ranges),
            content_type=doc["kind"],
            truncated=len(doc["text"]) > sum(end - start for start, end in ranges),
            extraction_version=2,
            passages=ranges,
            extracted_sha256=sha256(doc["text"].encode()).hexdigest(),
            discovered_from=doc["parent"],
        )
        sources.append(source)
        (output / f"S{index}.json").write_text(source.model_dump_json(indent=2))
    (output / "sources.json").write_text(
        json.dumps([s.model_dump() for s in sources], indent=2)
    )
    return sources
