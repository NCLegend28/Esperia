# Esperia

A personal agent city. Current implementation is a local research console; the city UI and unattended cloud deployment are later milestones.

## Execution policy: subscription only

Esperia research now runs through the official Codex CLI using your saved ChatGPT subscription login. There is no API-credit fallback in the research command. API-key variables and endpoint overrides are excluded from the child process. Run `codex login` and choose ChatGPT if login is needed; your existing .env.dev API key is not used or modified.

Research uses `--max-calls 16` rather than an API-dollar budget. Calls are sequential, each has a four-minute process timeout, and output length is an advisory target. Subscription limits are shared with your other Codex use. Failed or limited stages stop without switching to paid APIs; automatic cooldown resumption is not implemented yet. Claude subscription integration is a future adapter, not implemented here.

```sh
uv run esperia doctor
uv run esperia research "Compare the documented quantum businesses and identify evidence gaps." --max-calls 16
```

The evidence archive, review checks, and report outputs are unchanged. Historical API attempts remain in the ledger for audit; subscription jobs record zero API-dollar usage and a separate call limit. Before cloud deployment, the server will need an authorized Codex login and secure runtime setup.

Official references: [Codex authentication](https://learn.chatgpt.com/docs/auth), [non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode).

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
uv run esperia research "Compare quantum businesses over five years; identify missing evidence before any buy or sizing decision." --max-calls 16
uv run esperia jobs
uv run esperia calls JOB_ID
```

`collect` makes no model calls. `research` uses your Codex subscription and stores public research artifacts under gitignored `.local/dev/research/JOB_ID/`. Do not supply personal financial documents until encrypted portfolio storage is implemented.

### Reuse a recent source archive

```sh
uv run esperia research "Compare the documented quantum businesses and explain evidence gaps." --archive .local/dev/research/JOB_ID/evidence --max-calls 16
```

Archives are checked against raw content hashes and extracted text and must be less than 48 hours old. They contain issuer disclosures, not independently verified facts. Source text sent to the model is limited to 12,000 characters per page; truncation is disclosed. Sources in `config/quantum-sources.json` are a starter set and are not sufficient by themselves for a decision-ready investment report. PDFs, automatic source discovery, market prices, brokerage imports, and independent technical corroboration remain future work.

## Cost and failure behavior

Subscription jobs are bounded by call count and process runtime, not API pricing. Token usage is recorded from CLI completion events. Historical dollar accounting remains for audit but is not used to bill subscription jobs.

No model can access the vault, execute trades or send external messages through this workflow. The owner console is trusted local administration, not a production authorization boundary. Failed checks leave a preliminary report blocked; passing checks leaves it awaiting owner review. Owner acceptance UI is not yet implemented.

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
