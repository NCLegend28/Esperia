# Esperia

A local research console with durable jobs, bounded source collection, exact excerpt citations, independent review and separate owner acceptance. The city interface and cloud deployment remain future work.

## Product plan

- [Appearance and interaction](docs/appearance-spec.md): established city concept and proposed visual details.
- [Functional specification](docs/functional-spec.md): research-team behavior, capabilities and acceptance gates.
- [Roadmap](docs/roadmap.md): delivery phases, effort estimates, assumptions and decisions.
- [Task backlog](TASKS.md): priorities, dependencies, effort and completion criteria.

## Research any topic

```sh
uv sync --frozen
uv run esperia doctor --backend codex
uv run esperia research "Compare energy companies and their potential for growth over the next 5 years." --backend codex
```

With the default `source_search: "codex"`, omitting `--sources` and `--archive` makes a separately metered Codex search call select relevant public source URLs from the question. It records its chosen scope, entities, relevance explanations and limitations in `source-scope.json`. Broad questions receive a disclosed representative scope, not a claim of exhaustive coverage. No company list is silently substituted. Search results and documents remain untrusted evidence; models can still select irrelevant or unavailable pages, and failed collection or review leaves work blocked.

The collector then follows query-relevant links, archives original files and extracts HTML, text and PDFs. Search is enabled only for source planning. Drafting and reviewing use supplied evidence with browsing and other tools disabled. Source-planning model decisions use the selected execution mode and are included in `--max-calls`. Uncertain calls are never automatically replayed.

To supply sources explicitly, use a JSON array of public HTTPS URLs:

```sh
uv run esperia research "Compare these businesses" --sources my-sources.json --backend codex
uv run esperia discover "Cash flow and operational risks" --sources my-sources.json
uv run esperia collect --sources my-sources.json
```

`discover` and `collect` require an explicit manifest and make no model calls. The old quantum manifests under `config/` are opt-in examples. They are never default inputs. `--no-discovery` restricts research to its explicit/resolved seeds; it does not turn off the initial search if no seeds were supplied. `--archive PATH` reuses a verified, fresh archive and skips source search/collection.

## Shared search tools for local models

The new `source_search: "tools"` mode lets the selected model request bounded web searches through Esperia. It supports Ollama, llama.cpp and Codex inference without changing the research/citation pipeline. Local-only runs never instantiate a cloud search model. Every model decision is metered; tool calls have a separate persistent allowance. The final source plan can select only result IDs actually returned by search.

Odysseus uses SearXNG, and Esperia can connect directly to its JSON search endpoint. The provided development configuration uses the dedicated Esperia development port (8082); change it for your service. The service must be running with JSON enabled.

```sh
uv run esperia --workspace . --config config/local-search.example.json research "Compare energy companies and their potential for growth over the next 5 years." --backend ollama
```

Use `--backend llama` for your existing llama.cpp server. The selected model still must fit the schema/context and pass research-quality checks; tool support is not a claim of model quality. `config/local-search.example.json` is opt-in and does not change other jobs' configuration.

Search endpoint, calls, result count, query/text lengths, download/output bounds and timeout are configurable under `search`. Endpoints must be public HTTPS or an explicitly configured literal loopback service; redirects and proxy inheritance are disabled. Credentials in endpoint URLs are rejected. Search snippets are discovery metadata, not evidence: chosen pages must still be collected and archived before analysis.

Job artifacts include `source-tools.json`, `source-step-N.json`, `source-tool-observations.json`, `source-scope.json`, and `tool-calls.sqlite`. Inspect tool records with a read-only SQLite viewer. Unknown tools/arguments fail before dispatch; failed or interrupted tool calls stop the job without automatic replay. The separate `investigate` command adds multi-tool investigation and explicit checkpoint resume; uncertain calls still require inspection.

A separate Esperia development instance is configured on `127.0.0.1:8082`. The owner-local `esperia.json` enables it, so the usual `uv run esperia research "..." --backend ollama` command uses shared search without requiring a manifest. That file is ignored by Git; other installations must configure their own service.

Manage the isolated development service:

```sh
docker compose --env-file .local/dev/search/compose.env -f compose.search.yml up -d
docker compose --env-file .local/dev/search/compose.env -f compose.search.yml ps
docker compose --env-file .local/dev/search/compose.env -f compose.search.yml stop
```

For a fresh installation, first pull/review an official SearXNG image and obtain its immutable digest. Run `uv run scripts/configure_search.py --image REGISTRY/IMAGE@sha256:DIGEST` to generate a private secret and development connection files, then start the service. Port, CPU and memory bounds are explicit script options. The generated profile can be used with `--workspace . --config .local/dev/search/esperia.json`; activation of the root owner configuration is separate. Do not commit `.local` files. This service runs while Docker and this host are awake; it is not unattended cloud deployment.

See [foundation verification and limitations](docs/tool-foundation.md).

## Adaptive investigation

```sh
uv run esperia investigate "Compare energy companies and their potential for growth over the next 5 years." --backend ollama
uv run esperia agent JOB_ID
uv run esperia agent JOB_ID --action pause
uv run esperia agent JOB_ID --action resume
uv run esperia agent JOB_ID --action stop
```

The worker chooses search/read actions based on the evidence it has seen, then hands verified archives to the existing report and review checks. It can investigate a different source after an unavailable page. Saved checkpoints support explicit pause/resume without repeating completed model calls; uncertain outcomes stop without replay. Repetition, time, decision and per-tool budgets bound execution. The default economy job reserves up to 12 model calls; choices are configurable under `agent` and `search`. The existing `research` command remains available.

See [execution framework](docs/execution-framework.md) for controls, configuration, recovery boundaries and live verification. This is a single-worker foundation; team coordination and the city are not yet implemented.

## Configuration and profiles

Copy `esperia.example.json` to `esperia.json` in the workspace and edit the choices you need. Omitted fields inherit validated defaults from `src/esperia/settings.py`. Unknown fields, invalid limits and inconsistent budgets fail before generation. Do not put secrets in this file: public resolved configuration is saved with each job.

```sh
uv run esperia config
uv run esperia --config /path/to/esperia.json config
uv run esperia --workspace /path/to/Esperia research "Explain advances in battery recycling" --backend codex
uv run esperia research "Compare energy companies over five years" --profile config/profiles/investment.json
```

Global options (`--config`, `--workspace`, `--env`) go before the command. `--profile`, `--backend`, `--mode` and `--max-calls` are command options. `config` prints all resolved public choices without opening a model connection. `ESPERIA_CONFIG` can select the configuration file. With an explicit config file, its parent is the default workspace; otherwise the current directory is used. `--workspace` overrides that base. Environment files, relative manifest/archive/profile paths, the data root and database resolve against that workspace.

Configuration includes role-specific models, reasoning effort, source policy, research profile/checklist, crawl ranking and limits, excerpt sizes, provider timeouts/temperatures, call policy, repair limits and API-accounting rates. The general profile imposes no company list, financial checklist or fixed horizon. The optional investment profile demonstrates domain-specific instructions and discovery terms. Custom profiles are JSON objects with `name`, `version`, `checks`, `instructions`, optional `source_instructions` and `discovery_terms`.

The default data root is `.local/dev`; jobs, research/cache and evidence live beneath it. `data_root`/`ESPERIA_DATA_ROOT` relocates all of those together. A separate `database`/`ESPERIA_DATABASE` is an explicit override for the database alone. Existing databases and artifacts are not migrated automatically.

Existing environment overrides remain supported: `ESPERIA_MONTHLY_CENTS`, `ESPERIA_JOB_CENTS`, `ESPERIA_CODEX_BIN`, `ESPERIA_OLLAMA_URL`, `ESPERIA_OLLAMA_MODEL`, `ESPERIA_OLLAMA_CONTEXT`, `ESPERIA_OLLAMA_TIMEOUT_SECONDS`, `ESPERIA_LLAMA_URL`, `ESPERIA_LLAMA_MODEL`. Environment overrides take precedence over file settings; command options take precedence for their individual choices. `.env.dev` does not override an already-set environment value. Staging/production execution is deliberately disabled until deployment support exists.

Every research/repair job saves `resolved-config.json`; `request.json` also records the actual question and, for CLI research, the selected backend, mode and call cap. Behavior-changing settings, profile content, schemas, source content, UTC date and provider identity are included in cache keys. Cache reuse remains separate from verified source-archive reuse. `--refresh` bypasses stage result reuse. Old stage caches are not reused across the citation-strategy change.

## Source security and collection bounds

An empty `allowed_hosts` allows public HTTPS DNS names across topics. A nonempty list restricts sources to those exact hostnames. It cannot authorize private networks. URLs with credentials, IP literals or custom ports are refused. The collector checks DNS, rejects private/non-global or mixed public/private answers, pins the connection to the checked public address, and preserves the original TLS hostname. Each redirect goes through the same policy. Proxy inheritance is disabled. HTTPS verification, quote integrity and owner approval are enforced invariants.

Default discovery limits are 18 documents, 36 requests and depth two. Query ranking preserves short terms such as oil, gas, wind and LNG; an explicit profile can add domain terms. Budgets, weights, link exclusions and timeouts are configurable. Collection remains bounded link traversal, not exhaustive web coverage. It may miss script-rendered material, inaccessible documents or relevant links. Selected passages can omit context. PDF extraction has page, stream, text and runtime bounds; OCR is not implemented. Tables require layout verification before using extracted numbers.

Archives revalidate raw hashes, extracted content and passage ranges, and must satisfy the configured freshness window (default 48 hours). A changed host policy also applies when loading an archive. Missing seed coverage blocks acceptance in both research modes.

## Models, calls and quotation validation

| Backend | Analysis | Independent review | Automatic source search |
| --- | --- | --- | --- |
| `codex` | Configured Codex worker | Configured Codex reviewer | Codex by default, or configured shared tools |
| `ollama` | Installed local Ollama | Same local model, separate call | Shared tools when configured; otherwise explicit sources/archive |
| `ollama-hybrid` | Installed local Ollama | Codex | Codex by default, or configured shared tools |
| `llama` | Existing llama.cpp server | Same local model, separate call | Shared tools when configured; otherwise explicit sources/archive |
| `hybrid` | Existing llama.cpp server | Codex | Codex by default, or configured shared tools |

Local-only backends never silently invoke cloud search. Local endpoints remain loopback-only, omit credentials and reject redirects/proxy inheritance. Ollama verifies installed local weights; no downloads or remote models are enabled. Local inference requires the host to remain awake.

All drafting providers now select existing excerpt IDs. Esperia resolves quotation text and source identity deterministically and rejects invented IDs. Deep-mode source analysts do the same. Raw selections and resolved analysis are retained. This prevents generated quote-string errors and mismatched quote/source pairs; it cannot prove that a model's interpretation follows from an excerpt. The independent reviewer receives original selected source text, and failed checks block owner acceptance. Invalid selections, citations and reviewer checklists produce durable repair diagnostics.

Economy mode uses two inference calls, with one optional revision; Codex source planning adds one call. Shared-tool source planning reserves `search.max_calls + 1` model calls (up to one decision per search plus final selection), with a separate tool-call allowance. A revision remains blocked pending independent re-review. Deep mode needs one plan, one analysis per source, one draft and one review, plus two calls per optional revision. Its default budget is derived from configured document/revision limits (25 calls with default explicit sources; 26 with automatic search), bounded by `max_calls`. An explicit `--max-calls` is never silently increased. After collection, deep mode refuses an insufficient remaining budget before analysis. It saves the reviewed blocked report instead of dispatching a revision without room for another review.

Codex uses saved ChatGPT login with API credentials excluded from its environment, no API fallback, no automatic generation retries and a configurable per-stage timeout. Source search may perform multiple web tool operations inside its one bounded Codex process. Call limits are not token/usage guarantees. The API adapter and dollar accounting remain library functionality; rates are explicit configuration, not live pricing. Account-level subscription usage is shared with other Codex use.

## Review and repair

```sh
uv run esperia jobs
uv run esperia calls JOB_ID
uv run esperia review JOB_ID
uv run esperia accept JOB_ID --report-sha256 HASH
uv run esperia reject JOB_ID --report-sha256 HASH --reason "What needs changing"
uv run esperia repair JOB_ID --plan
uv run esperia repair JOB_ID --backend ollama --sources improved-sources.json
```

Use actual job IDs and the displayed report hash. Acceptance requires an unchanged registered report, passing checks and settled calls. These are trusted local-owner commands, not a network authorization interface. Acceptance authorizes no trade, payment or external message.

Repair refetches original sources or the explicit replacement manifest, retains parent history, assigns saved blockers, and independently evaluates each task. Repeated identical dispatch is refused. By default it inherits a parent's saved research profile unless an explicit configuration/profile replaces it. It uses the current operational configuration and saves that resolved configuration with the child. It does not recursively repair, silently re-search sources or automatically retry uncertain calls. The CLI still has no billing reconciliation control; preserve uncertain jobs for manual reconciliation.

Public research artifacts are not encrypted portfolio storage. Do not supply private financial documents or secrets until private storage is implemented. No live research-quality benchmark or investment evaluation gate is implied by passing software tests.

## Checks

```sh
uv run pytest -q
uv run ruff check src tests
uv run black --check src tests
uv run mypy src
uv run pip-audit
uv build
```

CI uses the locked environment. The current uv installation has no `audit` command, so dependency auditing uses `pip-audit`. See `docs/configuration-remediation.md` for this change's scope and validation.
