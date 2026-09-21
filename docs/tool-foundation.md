# Shared research tools — September 18, 2026

## Delivered slice

A typed tool registry and per-job SQLite journal enforce explicit grants, strict request/result validation, atomic call reservation and output budgets. Successful results are persisted. Failed or interrupted dispatch blocks subsequent tool execution rather than replaying automatically. This is a synchronous foundation; worker leases, owner cancellation and reconciliation/resume are not implemented here.

A provider-neutral source-discovery loop allows the selected inference backend to request a search and then choose observed result IDs. Esperia resolves those IDs to URLs. The existing collector still validates and archives documents, and existing excerpt/citation/coverage/review gates still apply. Tool observations cannot grant tools or change budgets. Source discovery has no result cache; each new job gets fresh search observations.

Tool calls and model calls have independent limits. The configured maximum search calls plus one final selection decision are reserved in model-call preflight, leaving the existing analysis/review allowance intact. Requests rejected before tool dispatch consume no tool call. An executed failure consumes its reservation. Generic tool failures never persist raw exception messages.

## Odysseus connection

User-selected reference: [odysseus-dev/odysseus](https://github.com/odysseus-dev/odysseus), inspected at commit `3b6c169162330cd35c4ce6d14949ef15fd3208a2`.

Its [search specification](https://github.com/odysseus-dev/odysseus/blob/3b6c169162330cd35c4ce6d14949ef15fd3208a2/specs/search.md) and [SearXNG configuration](https://github.com/odysseus-dev/odysseus/blob/3b6c169162330cd35c4ce6d14949ef15fd3208a2/config/searxng/settings.yml) identify a JSON-enabled SearXNG service. Esperia connects to that service over its [documented HTTP interface](https://docs.searxng.org/dev/search_api.html). No Odysseus source code was copied, and Esperia does not import or run its wider app/tool framework.

The inspected Odysseus container uses port 8081 but depends on the unmounted external drive. The owner chose a separate local instance for Esperia. No existing Odysseus container or volume was modified.

Esperia's isolated `esperia-search-dev` Compose project is healthy on `127.0.0.1:8082`, with 1 CPU, 512 MB memory and a separate cache volume. The downloaded official SearXNG image is pinned to `searxng/searxng@sha256:e0027a772aeeea55bf642256aae6fb3344ffa5f25ca665898c2ea821101334c4`. Configuration and a freshly generated secret are under ignored `.local/dev/search/`; secrets are not printed. `scripts/configure_search.py` exposes image, port and resource choices. `compose.search.yml` provides start/stop/recreation without touching other services.

The ignored owner-local `esperia.json` selects shared tools and that endpoint. `config/local-search.example.json` is an editable example for other installations. Public HTTPS services use DNS pinning. Literal loopback HTTP/HTTPS is allowed only for the configured search service; source URLs remain subject to public HTTPS policy. Redirects, URL credentials and proxy inheritance are disabled.

## Verification

- Reproduced the existing baseline: 136 tests passed.
- Added 33 regression cases: 169 total tests passed.
- Ruff, Black check and strict Mypy passed (24 source modules).
- Source distribution and wheel built successfully. No dependencies or lockfile changes were required.
- Tests use controlled HTTP/model fixtures. They cover independent call accounting across runtime instances, concurrent dispatch, interruption, malformed requests/results, ungranted tools, oversized output/downloads, forbidden source URLs, redirects, missing configuration, preflight call bounds, local/cloud routing and invented source IDs.
- The regression suite itself uses no live models. Separate live checks below verify connectivity and source-loop execution, not full research quality. Initial development cases and engineering gates are in `config/evaluations/research-tools-v1.json`; held-out owner-reviewed quality evaluation remains pending.

## Live development checks

- A real public search returned eight results, including EIA annual and short-term outlook pages. Saved at `.local/dev/verification/search-foundation-live.json`. Some upstream search engines were unavailable; the limitation is retained.
- Ollama verified installed local `qwen2.5:7b` weights and context capacity.
- The actual local model completed a bounded source-only diagnostic using two inference decisions and one search, with no cloud inference. It selected three observed URLs and saved the scope/limitations. Artifacts: `.local/dev/verification/source-loop-ee6d4a99-974b-465c-a5f7-2725d6b80971/`.
- That diagnostic produced no research report and is not owner acceptance. Some selected materials were older than the current year; source freshness, entity coverage and report quality still require evaluation. Source-planning prompts now include the current UTC date to make temporal context explicit.

## Remaining work

Complete end-to-end research-quality evaluation, broader fetch/archive-read tool contracts and cancellation/reconciliation before calling M1 complete. The persistent team notebook, delegation, city interface, Library, University and simulated economy remain later tasks.
