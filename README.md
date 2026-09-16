# Esperia

A personal agent city. Current implementation is a local research console; the city UI and unattended cloud deployment are later milestones.

## Research modes and model connections

Research defaults to economy mode: one combined analysis/draft and one independent review call, with at most one optional revision (three total calls). Missing evidence stops the loop. A revised draft stays blocked pending a fresh review; passing the original review still requires owner acceptance.

Validated economy stages are cached under `.local/dev/research/cache/`. Reuse requires the same question, UTC date, source content, instructions, schema, model/backend identity and output limit. Ollama identity includes the installed model digest and context setting. `--refresh` bypasses this cache; source archive reuse is separate. Deep mode retains the planner and per-source analysts, with a default limit of 16 calls. Call limits do not guarantee a particular amount of subscription usage.

| Backend | Analysis and revisions | Reviewer |
| --- | --- | --- |
| `codex` (default) | Codex subscription | Codex subscription |
| `ollama` | Installed local Ollama model | Same local model, separate call |
| `ollama-hybrid` | Installed local Ollama model | Codex subscription |
| `llama` | Existing llama.cpp server | Same local model, separate call |
| `hybrid` | Existing llama.cpp server | Codex subscription |

```sh
uv run esperia doctor --backend ollama
uv run esperia research "Compare quantum businesses over five years; identify missing evidence before any buy or sizing decision." --backend ollama-hybrid
uv run esperia research "Compare the documented quantum businesses and explain evidence gaps." --backend ollama
uv run esperia research "Compare the documented quantum businesses and explain evidence gaps." --mode deep --max-calls 16
```

The Ollama default is the already-installed `qwen2.5:7b`. Override `ESPERIA_OLLAMA_MODEL`, `ESPERIA_OLLAMA_URL`, and `ESPERIA_OLLAMA_CONTEXT` in `.env.dev` to use another installed text model. Default context is 32,768 tokens; the connector verifies model capacity but has no exact input-token preflight. Very large prompts can still exceed context, and larger contexts increase memory requirements. Local report quality has not been benchmarked; a successful connection is not an investment-analysis evaluation gate. Ollama cloud models are rejected, and no model downloads occur.

Standalone llama.cpp uses an owner-started `llama-server`, with `ESPERIA_LLAMA_URL` (default `http://127.0.0.1:8080`) and optional `ESPERIA_LLAMA_MODEL`. Configure sufficient context in the server. Both local connectors accept loopback endpoints only, omit credentials, disable redirects/proxy inheritance, and never fall back to a cloud provider. Local inference runs only while its host is awake.

Codex uses your saved ChatGPT subscription login. API-key variables and endpoint overrides are excluded from its child process; no API-credit fallback exists. Subscription limits are shared with your other Codex use. Each call has a four-minute timeout and failures stop without automatic retry. Claude subscription integration and automatic cooldown resumption remain future work.

References: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [Ollama chat API](https://docs.ollama.com/api/chat), [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

## Implemented

- Durable jobs, monthly/per-job reservations, per-call metering and approval holds.
- Public HTML/text retrieval from a fixed allowlist, bounded downloads, dated content-addressed snapshots and verified archive reuse.
- OpenAI-backed planner, evidence analysts, writer and independent reviewer with two maximum revision rounds.
- Exact-quote checks, fixed review criteria, source-linked Markdown reports and separate owner-review status.
- No automatic model retries. Known billing rejections release unused budget; unknown outcomes preserve reservations.
- Decimal-based portfolio-impact and constant-burn runway calculations (standalone helpers; company financial inputs are not yet extracted into a calculation pipeline).

## Start

```sh
uv sync --frozen
uv run esperia doctor
uv run esperia collect
uv run esperia research "Compare quantum businesses over five years; identify missing evidence before any buy or sizing decision."
uv run esperia jobs
uv run esperia calls JOB_ID
```

`collect` makes no model calls. `research` uses the selected backend and stores public research artifacts under gitignored `.local/dev/research/JOB_ID/`. Do not supply personal financial documents until encrypted portfolio storage is implemented.

### Reuse a recent source archive

```sh
uv run esperia research "Compare the documented quantum businesses and explain evidence gaps." --archive .local/dev/research/JOB_ID/evidence --max-calls 16
```

Archives are checked against raw content hashes and extracted text and must be less than 48 hours old. They contain issuer disclosures, not independently verified facts. Source text sent to the model is limited to 12,000 characters per page; truncation is disclosed. Sources in `config/quantum-sources.json` are a starter set and are not sufficient by themselves for a decision-ready investment report. PDFs, automatic source discovery, market prices, brokerage imports, and independent technical corroboration remain future work.

## Cost and failure behavior

Subscription jobs are bounded by call count and process runtime, not API pricing. Token usage is recorded from CLI completion events. Historical dollar accounting remains for audit but is not used to bill subscription jobs.

No model can access the vault, execute trades or send external messages through this workflow. The owner console is trusted local administration, not a production authorization boundary. Failed checks leave a preliminary report blocked; passing checks leaves it awaiting owner review. Owner acceptance is available in the local console; a graphical inbox is not yet implemented.

Uncertain calls are not automatically replayed. The current console does not expose billing reconciliation; do not clear reservations without checking provider activity. Cross-month job dispatch is blocked pending reconciliation, and outstanding historical reservations count toward the new month's capacity. Paid response artifacts and usage persist before output validation; a crash between provider completion and local persistence still requires reconciliation.

## Checks

```sh
uv run pytest -q
uv run ruff check src tests
uv run black --check src tests
uv run mypy src
uv run pip-audit
uv build
```

CI uses the locked environment and these checks. The installed uv has no `audit` command, so the locked `pip-audit` dependency runs through uv. It audits dependencies, not the local Esperia package itself.

See [build specification](docs/build-spec.md), [research contract](docs/research-contract.md), [milestones](docs/milestones.md), and [verification record](docs/verification.md).

## Owner review and follow-up work

`uv run esperia review JOB_ID` inspects an actual ID from `esperia jobs`, without generating text or contacting a model. It shows the report path, registered SHA-256 version, calls, validation blockers, consolidated follow-up tasks, any owner decision, and `can_accept`.

New economy and deep reports save `followups.md` and `followups.json` alongside the report. Every failed reviewer check and requested correction is included, as well as the draft's missing evidence. These are pending work items; the explicit `repair` command dispatches them within a bounded job. Old jobs derive the same list from saved outputs where available. A revised draft retains earlier findings as pending until independently reviewed again.

After reading a report that has `can_accept: true`, run `uv run esperia accept JOB_ID --report-sha256 HASH`, replacing both placeholders with the displayed values. To reject it, use `uv run esperia reject JOB_ID --report-sha256 HASH --reason "What needs changing"`. Decisions are durable, recorded once, and tied to the unchanged reviewed report. Blocked, changed, unregistered historical, or already-decided reports cannot be accepted. Historical jobs are never promoted automatically. Rejection is recorded but does not yet dispatch revision work.

These commands are for the trusted local owner only and must not be exposed to agents or a network service. Accepting research records satisfaction with that artifact; it does not authorize trades, payments, messages, or any external action. Reason text stays in the local database; do not include secrets or portfolio details until private storage is implemented.

## Bounded repair jobs

Preview assignments without model calls using `uv run esperia repair JOB_ID --plan` (replace JOB_ID with an actual ID). Validation errors now join draft gaps and reviewer findings as assigned tasks. Work is batched into one researcher/corrector call and one independent reviewer call; assignments describe workflow roles, not separate running processes.

Execute with `uv run esperia repair JOB_ID --backend ollama` for local-only work, or `--backend ollama-hybrid` for a local worker and a Codex subscription reviewer. The repair default is local Ollama. Repairs use two calls, skip response-cache reuse, and never launch recursive repairs. The default call cap is two. Each assignment requires a specific review verdict in addition to the standard checklist before the report can await owner acceptance.

Original seed URLs are refetched and relevant document links are followed, so expired evidence archives are not silently reused. To supply additional evidence, pass `--sources config/repair-sources.json`, a JSON array of up to 12 distinct approved HTTPS URLs; this **replaces** the original manifest, so include originals you still need. Sources remain restricted to approved hosts; discovery adds PDF support. General web search and live market feeds are not implemented. Bounded linked-filing discovery and PDF extraction are now enabled by default (see below). Refetching the same source set may leave evidence gaps unresolved.

Each child stores its plan, evidence, task verdicts and report. `review` shows parent/child links and assignment states. Parent history stays unchanged. Repeating an identical dispatch is refused and shows the existing child ID; uncertain calls must be reconciled rather than replayed. A failed reviewed child can itself be repaired with improved sources. Collection failures remain cancelled with blocked assignments; retry/reconciliation controls for these jobs are future work. Legacy jobs fall back to their saved title if no full question was recorded.

## Local evidence selection

Local economy/repair drafting now selects numbered exact excerpts instead of writing quotations. Esperia constructs the quoted text and source ID from the archived source, rejects unknown excerpt IDs, and sends the resolved claims plus original sources to the reviewer. `analysis-selection.json` preserves raw model output; `analysis.json` records the resolved claims, and `excerpt-catalog.json` records character offsets. Subscription drafting retains its existing exact-quote validation. Deep mode is unchanged.

This prevents fabricated quote strings and mismatched source IDs in selected citations; it does not establish that a model's statement follows from its selected excerpt. The reviewer must still reject unsupported claims, issuer marketing presented as fact, and conclusions about what a company has never disclosed. Missing evidence remains unresolved rather than becoming a quotation. No extra model call is added.

## Source discovery and public filings

Research and repair commands now enable bounded source discovery by default. `--no-discovery` retains the earlier explicit-manifest collector. Run discovery alone without model calls:

```sh
uv run esperia discover "Quantum businesses: financial statements, cash flow, dilution, valuation evidence and risks"
```

The printed archive path can be supplied to `research --archive ACTUAL_PATH`. Discovery visits relevant links from the supplied seed pages, prioritizes annual/quarterly filings and financial disclosures, and extracts text-based PDFs as well as HTML. This is issuer-site link discovery, not general search-engine coverage. It follows only approved HTTPS hosts, checks redirects, makes at most 36 requests across 18 documents by default, and stops at depth two. Collection is spread across seeds. Failures and out-of-policy links are recorded; access denials are not bypassed.

Each archive contains original downloaded files, complete bounded extracted text, source metadata, passage offsets, and `discovery.json` with the link trail, failures and coverage. Selection considers passages across the whole document instead of its first 12,000 characters. The total model evidence budget is 60,000 characters with explicit excerpt breaks. Archives revalidate raw hashes, regenerated extracted text hashes, passage ranges and freshness. Legacy archives remain supported.

PDF downloads are capped at 25 MB, extraction at 300 pages/two million text characters and 45 seconds in a subprocess. Scanned/encrypted/oversized documents may remain unavailable; OCR is not implemented. PDF table layout and selected passages can lose context, so neither extracted values nor keyword matches establish financial correctness. Reports disclose collection coverage; missing seed coverage prevents acceptance. Relevant filings can still be missed because of crawl limits, scripts, unsupported hosts or inaccessible links.

Independent technical corroboration, live market prices, complete security identity resolution and portfolio-aware sizing remain separate work. More documents improve the evidence base but do not make a report decision-ready automatically. The reviewer and owner gates still apply.

Implementation reference: [pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

The discovery defaults use `config/quantum-discovery-seeds.json`, with financial-result and filing indexes for the quantum-company research project. The older `config/quantum-sources.json` remains available for explicit source-only collection. Repairs preserve their original seeds unless `--sources config/quantum-discovery-seeds.json` is supplied. Link traversal prioritizes relevant children of a financial index before unrelated sibling navigation.

## Local response timeouts

Ollama's default response wait is now 900 seconds, configurable with `ESPERIA_OLLAMA_TIMEOUT_SECONDS` (30–3600). Connection establishment stays capped at 10 seconds. Non-streaming local generation includes prompt processing and output generation before the response arrives; large research prompts can exceed four minutes on a Mac. `doctor --backend ollama` displays the configured wait. Codex's existing timeout is unchanged. Provider failures now save a specific stage error that appears under `review` blockers; uncertain calls are never retried automatically.
