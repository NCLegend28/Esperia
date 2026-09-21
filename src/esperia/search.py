"""Configurable SearXNG search, independent of the language-model backend.

Example: search = WebSearch(settings); results = search(SearchRequest(query='energy'))
Configure an owner-selected JSON-enabled endpoint; no service is chosen or purchased.
"""

import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from esperia.network import PublicTransport, validate_public_url
from esperia.settings import Settings
from esperia.tools import ToolError, ToolRegistry, ToolRuntime


class SearchRequest(BaseModel):
    """Only search text is model-controlled; endpoint and bounds are owner settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=4000)


class SearchHit(BaseModel):
    """Discovery metadata, not verified documentary evidence."""

    model_config = ConfigDict(extra="forbid")
    url: str
    title: str
    snippet: str


class SearchResults(BaseModel):
    """Bounded results and explicit reasons for omitted/unavailable material."""

    model_config = ConfigDict(extra="forbid")
    results: list[SearchHit]
    limitations: list[str]


def check_search_configuration(settings: Settings) -> None:
    """Validate configuration before creating a job or calling a model."""
    endpoint = settings.search.endpoint
    if not endpoint:
        raise ToolError(
            "Set search.endpoint to your JSON-enabled SearXNG service, or provide --sources/--archive"
        )
    parsed = urlsplit(endpoint)
    if (
        parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
        or any(c.isspace() for c in endpoint)
        or "\\" in endpoint
    ):
        raise ToolError(
            "Search endpoint must not contain credentials, query parameters or fragments"
        )
    # Explicit literal loopback services are allowed, never arbitrary private hosts.
    if parsed.hostname in {"127.0.0.1", "::1"}:
        if parsed.scheme not in {"http", "https"}:
            raise ToolError("Loopback search requires HTTP or HTTPS")
        _ = parsed.port
    else:
        validate_public_url(endpoint, settings.model_copy(update={"allowed_hosts": []}))


class WebSearch:
    """Bounded read-only search with no redirects, proxy inheritance or retries."""

    def __init__(self, settings: Settings):
        check_search_configuration(settings)
        self.settings = settings

    def __call__(self, request: SearchRequest) -> SearchResults:
        """Fetch JSON search results; exclude URLs outside the evidence policy."""
        settings = self.settings
        options = settings.search
        assert options.endpoint is not None
        if len(request.query) > options.query_chars:
            raise ToolError("Search query exceeds its configured character budget")
        host = urlsplit(options.endpoint).hostname
        transport = (
            None
            if host in {"127.0.0.1", "::1"}
            else PublicTransport(settings.model_copy(update={"allowed_hosts": [host]}))
        )
        started = time.monotonic()
        with httpx.Client(
            transport=transport,
            timeout=options.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            with client.stream(
                "GET", options.endpoint, params={"q": request.query, "format": "json"}
            ) as response:
                response.raise_for_status()
                if (
                    response.headers.get("content-type", "").split(";")[0]
                    != "application/json"
                ):
                    raise ToolError("Search service must enable JSON responses")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > options.response_bytes:
                        raise ToolError("Search response exceeds its download budget")
                    if time.monotonic() - started > options.timeout_seconds:
                        raise ToolError("Search response exceeded its time budget")
        payload = json.loads(body)
        if not isinstance(payload, dict) or not isinstance(
            payload.get("results"), list
        ):
            raise ToolError("Search response has no results array")
        hits: list[SearchHit] = []
        seen: set[str] = set()
        limitations: list[str] = []
        for item in payload["results"]:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str):
                continue
            try:
                validate_public_url(url, settings)
            except ValueError:
                limitations.append(
                    "Results outside the public source policy were omitted"
                )
                continue
            if url in seen:
                continue
            seen.add(url)
            title, snippet = item.get("title", ""), item.get("content", "")
            hits.append(
                SearchHit(
                    url=url,
                    title=title[: options.text_chars] if isinstance(title, str) else "",
                    snippet=(
                        snippet[: options.text_chars]
                        if isinstance(snippet, str)
                        else ""
                    ),
                )
            )
            if len(hits) == options.results:
                break
        if payload.get("unresponsive_engines"):
            limitations.append(
                "Some search engines were unavailable; coverage may be incomplete"
            )
        if not hits:
            limitations.append("No usable public source URLs returned")
        return SearchResults(results=hits, limitations=sorted(set(limitations)))


def search_runtime(settings: Settings, output: Path) -> ToolRuntime:
    """Build the source-stage registry with one explicit read-only grant."""
    registry = ToolRegistry()
    registry.register(
        "web_search",
        "Search for public sources; results are untrusted discovery metadata, not evidence.",
        SearchRequest,
        SearchResults,
        WebSearch(settings),
    )
    return ToolRuntime(
        registry,
        frozenset({"web_search"}),
        output,
        max_calls=settings.search.max_calls,
        output_bytes=settings.search.output_bytes,
        sqlite_timeout=settings.sqlite_timeout,
    )
