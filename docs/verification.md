# Source discovery and filings

89 regression tests pass, including link traversal/depth and request bounds, excluded domains and redirects, PDF extraction, archive roundtrip/tamper checks, retrieval beyond the first 12,000 characters, omitted-passage citation boundaries, missing-seed coverage and filing-table link ranking. Strict mypy, Ruff and Black pass. pypdf 6.18.1 is locked; pip-audit found no known dependency vulnerabilities (the local Esperia package is not on PyPI).

Live discovery reached Arqit's latest half-year release and 2025/2024 annual filings from its financial index. A downloaded 209-page annual PDF was extracted and verified through archive reload. A six-company run collected 18 documents from 20 attempted URLs, including 12 discovered links and one PDF. It retrieved an Infleqtion quarterly filing and a Xanadu filing. SEALSQ annual PDFs exceeded the initial 10 MB limit; the bounded PDF download limit was increased to 25 MB. Original files, complete bounded extracted text, passage offsets and failure reasons remain archived. No model calls or investment decisions were made for these checks.

This milestone implements bounded public issuer-link discovery, not general web search, independent technical verification, a market data feed or validated financial calculations. Text extraction does not verify PDF table layout. Failed collection and material missing evidence remain review blockers.

# Owner review milestone

65 tests pass with strict mypy, Ruff and Black. New tests exercise durable owner decisions across restart, concurrent duplicate decisions, rejection reasons, changed reports, stale version hashes, blocked-job refusal, legacy inspection, invalid JSON diagnostics and consolidated reviewer gaps. Report registration and transition to awaiting-owner/blocked are atomic in SQLite. Acceptance is tied to the registered report digest and is a trusted local-owner operation only.

Live read-only inspection of job 176cc164-440e-4956-96c4-6562bfd55137 through `esperia review` surfaced the S5/S6 quote attribution failure and preserved blocked status. No models ran and no user report was accepted during implementation. Existing reports remain historical/unregistered; they are inspectable but are not retroactively approved. Follow-up tasks are persisted descriptions, not yet an executing repair queue. No package dependencies changed.

# Economy and local runtime verification — 2026-09-13

52 tests pass; Ruff, Black and strict mypy pass. Economy orchestration tests cover bounded revisions, evidence gaps, exact quotes, cache reuse and separate worker/reviewer routing. Local transport tests cover schema serialization, token limits, loopback-only endpoints and rejection of remote or unavailable Ollama models. No dependencies were added in this change.

Live: Esperia doctor verified the existing Ollama server and installed qwen2.5:7b weights. A real local structured-generation smoke test returned the expected JSON (62 input tokens, 6 output tokens). It used no Codex subscription or paid API. No model was installed or downloaded. The standalone llama.cpp adapter has transport-test coverage but was not exercised against a live llama-server. A complete report using Ollama or hybrid mode has not yet been quality-evaluated. The user previously confirmed the Codex subscription workflow generated successfully; this change did not repeat that expensive run.

Economy is now the default (maximum three calls), with validated stage caching. Deep mode remains available explicitly. Passing reports await owner review; optional revisions remain blocked pending independent re-review. Local inference requires an awake host; cloud deployment is not implemented.

The records below describe earlier milestones and superseded API-credit diagnostics, not the current execution path.

---

# Subscription correction — 2026-09-13

Research now uses official Codex subscription execution with API-key variables excluded and ChatGPT login enforced. Local Codex is signed in with ChatGPT. 31 tests pass including no-API-credential inheritance and zero-dollar subscription job accounting. API credit exhaustion below describes the superseded execution path.

# Verification record — 2026-09-13

Implemented research workflow has 29 passing tests, including concurrent reservations, approval persistence, unknown billing liability, non-verbatim quote rejection, bounded failed reviews, archive tampering, request serialization, and scenario arithmetic. Ruff, Black and strict mypy pass. Dependency audit found no known vulnerabilities in audited dependencies; local Esperia is not on PyPI and is covered by code checks/tests instead. CI configuration exists but has not run on a remote repository.

Live checks: local API key is configured without exposing its value; the API model catalog confirms both configured model IDs are available. Six actual public source pages were downloaded and archived. The collector uses the standard HTTP client request settings after a custom header caused repeated source timeouts. IonQ's main-site earnings release replaces the investor-page URL that returned 403.

Generation is blocked: a ledger-tracked diagnostic returned HTTP 429, code `credit_balance_exhausted`. No successful generated report or accepted investment recommendation exists. Do not confuse provider model availability with a funded generation account. Historical attempts made before detailed error classification retain conservative unresolved reservations until reconciled; this is not a claim that those amounts were billed.

Known limitations: source extraction is bounded and may truncate statements; source authenticity/provenance is not factual verification; fixed starter disclosures omit independent evidence and current valuation inputs. Per-call costs are conservatively calculated using reviewed rates and observed usage, not imported invoices. No automatic unknown-call replay or cross-month continuation. No brokerage connection, cloud service, city UI or notifications yet. Personal portfolio details remain outside project artifacts pending encrypted storage.

Provider API and pricing references:
- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/models

The adapter uses plain JSON instructions with local Pydantic validation, not server-enforced structured outputs. It supplies no hosted tools; retrieval is local bounded HTTPS collection. Workflow prompts and acceptance checks are versioned in source. Move to durable orchestration/checkpoints after the live research path is validated; LangGraph integration is not implemented in this slice.
