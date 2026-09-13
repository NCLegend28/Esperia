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
