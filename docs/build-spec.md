# Planning index — 2026-09-17

The established city concept below is retained. Current planning is split into [appearance and interaction](appearance-spec.md), [functional behavior](functional-spec.md), [delivery roadmap](roadmap.md) and [task backlog](../TASKS.md). These distinguish implemented capabilities from proposals. Quantum research below is the original example, not a global task scope. New visual details and timeline assumptions remain proposals until reviewed.

---

# Subscription execution amendment — 2026-09-13

The owner requires existing subscriptions, not API credits. The research console now uses official Codex non-interactive execution with forced ChatGPT login and no API-key fallback. Subscription call limits replace model-dollar reservations. The earlier API-first architecture and provider spending envelope below are historical proposals and superseded for model execution. Claude subscription support remains planned; scheduling and server authentication still require implementation.

# Esperia build specification

Status: approved concept; implementation begins with a local foundation. Project root is ~/projects/Esperia, an intentional exception to the external-drive default.

## Outcome

Assign a quantum investment research job, close the laptop, and return to a cited report with calculations, review outcomes, and costs, or an actionable blocker. The first release is occasional deep research. The owner is the sole user.

## City model

City Hall contains the mayor, budget ledger, approval inbox, and overall job board. Buildings represent projects or shared capabilities; floors represent divisions. Agents have stable identities independent of the model chosen for each run. Offices expose current task, model, actions, sources, artifacts, concise progress explanations, cost, and blockers. Animations reflect execution events without model calls. Idle and rate-limited avatars can visit homes or leisure buildings. Expansion is proposed by the mayor and requires owner approval.

## Modular architecture

Browser: React/TypeScript and React Three Fiber for navigation, with accessible ordinary panels for job inspection. API: Python/FastAPI, /v1 endpoints, typed inputs and structured errors. Workflow: LangGraph checkpoints behind provider-neutral adapters. Storage: PostgreSQL for jobs, steps, approvals, cost events, scoped memory metadata and agent versions; object storage for evidence and artifacts. Workers: persisted queue with leases, retries, schedules, deduplicated triggers, and recovery. Telegram delivers meaningful changes and links to authenticated decisions. Models are benchmarked on representative work before routing policies are chosen.

Keep domain modules independent: ledger, policy, jobs, providers, evidence, memory, review, notifications, portfolio, city projection. The city is a projection of server state; closing it never stops a job. No simulated jobs presented as real progress.

## Workflow and acceptance

Mayor scopes the request and reserves a budget. Verification planner defines checks before research. Researchers collect evidence; financial calculations run as reproducible code. Reviewer checks the evidence independently against the contract. Allow two revision rounds initially within the same envelope. Escalate on exhausted budget, ambiguous requirements or failed checks. Automated review and owner acceptance are distinct states; agents cannot weaken their own acceptance criteria.

## Permissions

Routine API use is automatic inside approved limits. Financial actions, paid commitments, secret changes, calendar changes, outgoing messages, and expansion require owner approval. Notify the owner on detected events with findings and proposed responses. File organization is allowed only in designated roots with a reversible manifest. Brokerage access is read-only, initially imports and later a verified Fidelity-compatible connector. No order-entry or transfer capability is included.

Owner-only vault management. Service connectors use scoped credentials without exposing values to prompts, logs, reports, or memory. City, building and agent memory have explicit access scopes, provenance, timestamps and versioning. Public source documents and generated reports may be privately stored in the cloud and analyzed by authorized models. Personal portfolio inputs stay private and are minimized before provider use. External documents are untrusted evidence, never instructions for tools or permissions.

## Deployment and reliability

One cloud server initially, external hosted model inference, browser-rendered graphics. Use Terraform and Docker, strict dev/staging/production separation, pinned dependencies, CI checks, health/readiness probes, structured scrubbed logs, encrypted off-server backups, and a tested restore/rollback procedure. Generated-code execution must be isolated from coordinator secrets and state before the app-building division is enabled. Cloud deployment and any purchase require owner approval after exact resources and cost are reviewable.

Before paid execution: reserve remaining per-job cost atomically before every call; limit output/tool budgets; meter actual usage; reconcile billing; handle cross-month jobs; bound retries; persist side-effect idempotency records. Rate limits become waiting states, not repeated immediate calls. Notifications are deduplicated. Approval records bind owner, action payload, scope, expiry and one-time consumption. Fail closed if policy or cost state is unavailable.

## Financial envelope

Monthly total $150 including $40 existing subscriptions. Proposed allocations: server $24; backups/storage $6; APIs/search/data $65; reserve $15. These are planning envelopes, not approved purchases or quotes. Initial per-job cap $5 is configurable and provisional; measure actual report costs before promising report frequency. Idle agents do not call models. Reserve model capacity for review.

## Improvement

Track factual accuracy, citation validity, acceptance, cost, time and repeat errors by task type and model/instruction version. Trainer proposes changes to instructions, tools, or examples; run held-out evaluations before adoption. No self-granted permissions, reward-based authority, or autonomous model-weight training.

## Open decisions

Exact model providers and API access; hosting region/vendor and reviewable quote; Telegram setup; verified Fidelity import formats/connectors; iCloud account confirmation; mobile interaction details. These do not block local ledger development.

## Documentation checked during planning

- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://r3f.docs.pmnd.rs/
- https://www.digitalocean.com/pricing/droplets
- https://developers.openai.com/api/docs/pricing
- https://core.telegram.org/bots/api

Recheck stable releases and pricing at each implementation/deployment milestone.
