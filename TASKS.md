# Esperia task backlog

Planning baseline: 2026-09-17. Task checkboxes track complete acceptance gates; partial implementation is recorded below. Estimates are focused delivery hours, not guarantees or automatic scheduled work. “Build” means Codex-assisted implementation when dispatched; “Owner” means Tali. One implementation lane is assumed. See [roadmap](docs/roadmap.md), [appearance](docs/appearance-spec.md), and [behavior](docs/functional-spec.md).

P0 = release gate; P1 = important experience/capability. Priority is relative to the assigned release, not a claim of a current production incident. Dependencies use E- task IDs. Completion requires recorded evidence and passing relevant tests, lint/type/security checks for changed code; a checked box alone is not acceptance.

## Implementation baseline

Existing CLI research/configuration/security remediation is recorded in [configuration remediation](docs/configuration-remediation.md). Its 136-test result is historical verification, not a new run or proof of live research quality. Existing changes are uncommitted; preserve and review them before implementation. Shared tool/source-discovery implementation began September 18; see the progress record below.

## Work queue

| Status | ID | Priority | Task | Hours | Depends on | Gate | Owner | Done when |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| [ ] | E-01 | P0 | Confirm pilot scope and evaluation thresholds | 4 | — | M0 | Owner + build | Versioned energy and nonfinancial cases; define relevance, support, numerical and resource gates before scoring. |
| [ ] | E-02 | P0 | Locate visual references and settle first-release style | 4 | — | M0 | Owner + build | Record reference paths, required traits, camera/art direction and desktop/mobile priority; unresolved choices remain explicit. |
| [ ] | E-03 | P0 | Record current live research baseline | 4 | E-01 | M0 | Build + owner | Run authorized bounded representative jobs; record rejection causes, relevant-source coverage and usage without confusing test success with quality. |
| [ ] | E-04 | P0 | Define shared tool contracts and capability registry | 8 | E-01 | M1 | Build | Typed requests/results, permission checks, call ledger, cancellation and resource bounds; invalid requests rejected. |
| [ ] | E-05 | P0 | Connect configurable search and retrieval | 12 | E-04 | M1 | Build | Fresh topic discovers relevant sources without a cloud language model; record provider, provenance and failures; preserve network protections. |
| [ ] | E-06 | P0 | Add bounded local-model tool loop | 12 | E-04, E-05 | M1 | Build | Ollama selects validated tools and uses returned evidence; malformed calls, limits and uncertain outcomes stop safely. |
| [ ] | E-07 | P0 | Verify backend parity and tool isolation | 8 | E-06 | M1 | Build | Local/cloud adapters share contracts; prompt-injected content cannot change grants; alternate topics and configurations pass. |
| [ ] | E-08 | P0 | Build versioned research notebook and hypothesis register | 10 | E-04 | M2 | Build | Persist author, scope, hypothesis, claim, source, date, assumptions, counterevidence and superseding revisions; enforce scope. |
| [ ] | E-09 | P0 | Track assignments and task dependencies | 8 | E-08 | M2 | Build | Owned bounded assignments with dependencies, status and artifacts; prevent duplicate ownership and orphaned tasks. |
| [ ] | E-10 | P0 | Compare independent findings and disagreements | 10 | E-08, E-09 | M2 | Build | Independent notes precede comparison; detect shared-source duplication and preserve a disagreement with a follow-up test. |
| [ ] | E-11 | P0 | Add adaptive research coordinator | 12 | E-07, E-10 | M2 | Build | Lead revises plan from evidence, allocates bounded follow-ups, reserves review capacity and records stopping reasons. |
| [ ] | E-12 | P0 | Make calculations isolated and reproducible | 10 | E-08 | M3 | Build | Rerun archived inputs with units, code and parameters; sandbox cannot access coordinator secrets; altered inputs invalidate dependents. |
| [ ] | E-13 | P0 | Normalize dated quantitative evidence | 10 | E-05, E-12 | M3 | Build | Public-source pilot adapter records availability date, period, currency and missing data; reject incompatible comparisons. Licensed feeds are optional separate scope. |
| [ ] | E-14 | P0 | Evaluate research-team pilot independently | 8 | E-03, E-11, E-13 | M3 | Build + owner | Functional scenarios A–D pass and owner reviews held-out energy/nonfinancial reports against thresholds from E-01; publish failures and usage. |
| [ ] | E-15 | P0 | Expose authenticated API and persisted events | 12 | E-09, E-11 | M4 | Build | Versioned API with validation, authentication, event replay and reconnect; client state reflects persisted jobs and decisions. |
| [ ] | E-16 | P1 | Approve annotated visual blueprint | 8 | E-02 | M4 | Owner + build | Reference sheet, screen flow, component states and accessible route accepted before scene implementation. |
| [ ] | E-17 | P1 | Build city navigation from live records | 16 | E-15, E-16 | M4 | Build | City Hall/building/floor/office selection maps to real jobs/agents; stable identities and event-driven activity; no fabricated work. |
| [ ] | E-18 | P0 | Build office, evidence and decision panels | 12 | E-15, E-16 | M4 | Build | Owner can inspect sources, calculations, dissent and blockers, then decide on exact artifact version; linked follow-ups preserve lineage. |
| [ ] | E-19 | P0 | Verify accessible and responsive workflows | 8 | E-17, E-18, E-26, E-27 | M4 | Build + owner | Keyboard-only panel route completes pilot; reduced motion, zoom, narrow screen, stale connection and error states verified. |
| [ ] | E-20 | P0 | Implement durable worker recovery and pause controls | 12 | E-11, E-15 | M5 | Build | Restart/lease expiry/cancellation/rate-limit tests preserve completed work, avoid duplicate execution and retain uncertain outcomes. |
| [ ] | E-21 | P0 | Prepare and validate always-on deployment | 12 | E-20 | M5 | Build + owner | Review exact runtime/model compatibility and resource quote; package environments/IaC, health checks and rollback. Deploy only after owner authorization; otherwise mark unattended gate blocked. |
| [ ] | E-22 | P0 | Prove backup and restore | 8 | E-20, E-21 | M5 | Build | Restore isolated environment from encrypted backup and verify jobs, evidence, approvals and notebook lineage; record recovery time. |
| [ ] | E-23 | P1 | Deliver meaningful deduplicated notifications | 8 | E-15, E-20 | M5 | Build + owner | Owner selects/authorizes channel; only configured actionable events delivered once, with quiet hours and authenticated links. |
| [ ] | E-24 | P0 | Run unattended beta acceptance and owner review | 12 | E-14, E-19, E-22, E-23, E-25, E-26, E-27 | M6 | Build + owner | Real authorized worker survives browser disconnect/restart; functional E–F pass; held-out reports meet frozen thresholds; owner accepts or records blockers. |
| [ ] | E-25 | P0 | Persist model-independent agent identity | 8 | E-08 | M2 | Build | Switch a model while preserving agent ID, history, scope and permissions; record per-run model and validate capabilities. |
| [ ] | E-26 | P0 | Enforce owner expansion decisions and overrides | 8 | E-11, E-15 | M4 | Build + owner | Mayor delegates within an approved envelope; financed expansion waits for version-bound approval; override invalidates conflicting queued work and records active-work limits. |
| [ ] | E-27 | P0 | Build discipline Library catalog and document viewer | 16 | E-08, E-15, E-16 | M4 | Build | Open archived public PDF/text by discipline, search across collections and inspect provenance; cross-list one artifact, enforce access controls and prevent active-content execution. |

Total estimated work: **260 hours**, plus approximately 20–25% contingency (**312–325 hours** overall). The owner confirmed no deadline; no weekly capacity or calendar dates are committed. Do not silently consume contingency by adding features.

## Next session

1. Resolve roadmap decisions D-01–D-06 where needed; confirm scope and release priority; delivery proceeds by phase gates without a deadline.
2. Complete E-01–E-03 and record baseline evidence. No paid tool/provider is assumed authorized.
3. Continue E-04–E-07 from the shared-tool foundation; the owner authorized implementation September 18. Full release gates remain pending live quality and recovery work.

## Completion record

For each completed task append: date, artifact/commit link, verification evidence, actual effort, unresolved limitations and owner decision where applicable. Update remaining effort and dependencies after scope changes.

## Later backlog — not included in the estimate

- Saved research watchlists and thesis-change alerts, only on explicit monitoring authorization.
- Read-only portfolio imports and permission-scoped account connectors.
- Reusable department/agent templates and owner-approved expansion.
- Evaluated instruction improvements; never self-approved release gates.
- Scenario exploration and additional city decoration.
- Architecture agents designing distinctive Esperia in-city buildings (scope confirmed); specify the building-design/preview/asset workflow and estimate.
- Additional useful disciplines selected from owner goals; no exhaustive city-profession roster.
- Broader data-provider coverage and full historical backtesting infrastructure.

## Scope update: owner decisions

E-25–E-27 add 32 estimated hours for explicit persistent identity, financing/override controls and Library viewing/organization. M2 must include E-25; M4 must include E-26–E-27 before its acceptance gate. Task IDs remain stable; row order is not execution order.

Future work to specify/estimate: attributable research-revenue scoreboard; competing strategy teams; University practice/evaluation; reputation and a internal simulated agent-investment economy (confirmed; rules and implementation still to define). These do not authorize trades or add financial actions to the first release.

## Implementation progress — September 18, 2026

- E-01 partial: initial versioned engineering gates and development cases in `config/evaluations/research-tools-v1.json`; owner-reviewed quality thresholds and held-out cases remain pending.
- E-03 partial: existing 136-test baseline reproduced; expanded suite passes 169 tests. Live local-model/search source-loop diagnostic passed, but full research quality is not yet established.
- E-04 partial: typed tool registry, explicit grants, atomic persisted call reservations, bounded output and fail-closed interruption handling. General cancellation/reconciliation and broader tool contracts remain pending.
- E-05 partial: SearXNG connector compatible with Odysseus's search service, configurable endpoint and network/resource limits. No upstream code was copied. The owner-selected separate local service is healthy and real search verified; records are in `docs/tool-foundation.md`.
- E-06 partial: structured source-discovery loop works with the selected local inference adapter and observed result IDs. Actual Qwen source-loop execution passed; full report quality and a general investigation loop remain pending.
- E-07 partial: deterministic adapter/routing, injection, budget, output and interruption regressions added. Full provider parity/live checks remain pending.

No milestone is marked complete solely because its first component exists. Library/city/collaboration/economy implementation has not begun.

## Implementation progress — September 20, 2026

- E-03 partial: recorded a full-pipeline local baseline that reached analysis selection and timed out at its configured 180-second diagnostic limit. End-to-end research quality remains unproven.
- E-06 partial: source search/finish constraints now appear in the generation schema; repeated identical queries reuse observations without another search dispatch; rejection diagnostics identify safe field paths and error codes. A fresh two-call Qwen source-only diagnostic passed.
- E-07 partial: mixed-action, diagnostic privacy and duplicate-search regressions pass; full suite now 175 tests, with Ruff, Black and strict Mypy passing. Live cloud parity remains pending.
- Current implementation, evidence locations and next sequence: [research status](docs/research-status.md). No complete milestone or accepted research report is claimed by this update.

## Execution framework progress — September 20, 2026

- E-04/E-05: adaptive jobs now grant observed-document reads alongside search, enforce separate tool caps and expose cooperative owner pause/stop controls. Unknown external outcomes remain blocked; automated reconciliation is not delivered.
- E-06: added the `investigate` command with a durable decision/action/observation loop, schema-level action availability, repetition/time/step limits, verified archive handoff and reserved analysis/review capacity. A fresh live Qwen search/read/handoff diagnostic passed. See [execution framework](docs/execution-framework.md).
- E-07: added deterministic cross-topic, retrieval failure/replanning, archive integrity, tool isolation, budget, concurrency, control and resume regressions. Full live backend parity and research quality remain pending.
- E-11/E-20 foundations: completed decisions and report stages can resume explicitly without new calls; model/input changes and uncertain outcomes stop. This is single-worker local execution, not multi-worker assignments, an unattended queue or distributed leases.
- Next: finish representative research quality evaluation, then E-08/E-25 (shared notebook and durable identities) before collaborative E-09–E-11. City/Library UI and the simulated economy remain future work.

Framework verification: 202 tests passed, with Ruff, Black and strict Mypy passing. Source-only live investigation passed; no full live report-quality acceptance is claimed.


## Follow-up: repeated-action recovery

Diagnosed owner job `e9549ef3-444f-4c88-a508-ca1115556698`: one search, three identical model requests, no reads. Added actionable feedback, one-decision tool redirection after duplication, schema-constrained unread document IDs and an independent read-selection gate. Fresh observations reset consecutive stalls; overall caps remain unchanged. Regression coverage now includes the normal three-search allowance instead of relying only on the earlier one-search live probe. The blocked job is preserved.

Recovery verification: 207 tests, Ruff, Black and strict Mypy passed. Live Qwen handoff passed using normal 3-search/10-decision/4-read limits: one actual search, four suppressed duplicate requests, four reads and two verified sources. Model planning remained repetitive; no report-quality acceptance is claimed. Evidence: `.local/dev/verification/repetition-recovery-153acaac-2cdf-46e0-a3c8-8d6f21a639b5`.
