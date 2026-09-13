# Milestone tracker

## 0 — Specification and local ledger
- [x] Capture scope, architecture, permissions and financial envelope.
- [x] Define first research contract without committing personal portfolio data.
- [x] Persistent jobs and atomic budget reservations.
- [x] Approval hold, single claim, settlement and cancellation.
- [x] Local console and meaningful concurrency/accounting tests.
- [x] Verify checks and dependency audit: 8 tests, Ruff, Black, strict mypy, package build; pip-audit found no known dependency vulnerabilities. CI added but not yet run remotely.

## 1 — End-to-end research
- [x] API key configuration, model availability check and per-call cost accounting.
- [ ] Live generation (blocked by API credit balance), provider-invoice reconciliation and comparative model evaluation.
- [x] Bounded retrieval, content-addressed snapshots, archive integrity checks and standalone scenario calculations.
- [ ] Automated discovery, independent corroboration, market prices and company-specific calculation inputs.
- [x] Planner/analyst/writer/reviewer workflow with bounded revisions, exercised with deterministic transport tests.
- [ ] Successful live end-to-end generation.
- [ ] Actual cited report and explicit owner acceptance.

## 2 — Unattended operations
- [ ] Authenticated API, PostgreSQL migration and durable worker recovery.
- [ ] Audited one-time action approvals and billing reconciliation.
- [ ] Terraform/Docker deployment with approved quote and separate environments.
- [ ] Restore test, restart test, scheduler and Telegram integration.

## 3 — City
- [ ] Navigable building/floor view tied to live server events.
- [ ] Agent inspection, conversations, job board and approvals.
- [ ] Rate-limit/idle state animations without model usage.

## 4 — Growth
- [ ] Read-only portfolio import then verified account connection.
- [ ] Scoped persistent memory and evaluated trainer proposals.
- [ ] Owner-approved expansion templates.
