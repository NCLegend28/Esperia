# Esperia functional specification

Version: 0.1 · 2026-09-17 · Status: planning draft

Confirmed owner direction: no deadline; first usable release is a working research team with a simple, live city view. Detailed visual polish follows later.

Purpose: define how the city works, independently of its appearance or model vendor. Companion documents: [appearance](appearance-spec.md), [roadmap](roadmap.md), [tasks](../TASKS.md). The owner asked to plan before implementing the next foundation; this document does not authorize new deployments, subscriptions or autonomous activity.

## 1. Product outcome

Esperia is a personal city of persistent, tool-using agents. The owner assigns a goal; the mayor organizes work, specialists investigate, agents exchange evidence, analysts test hypotheses, reviewers challenge conclusions and the owner receives an inspectable result or a specific blocker.

Research capability must be independent of the selected language model. A capable local model should be able to request internet search through Esperia's tool service, without requiring a cloud language model. Internet tools may still require network access or a separately selected search/data provider.

The initial vertical is public research with quant-style discipline. Additional departments are possible later, but investment research is neither a permanent global template nor authority to trade.

## 2. Implementation baseline, as recorded September 17

September 18 amendment: shared tool accounting and a configurable source-discovery loop are now implemented. See [foundation verification](tool-foundation.md) for tested behavior and remaining live-service/model gates. The table below describes the previous baseline.

| Implemented in code | Limitation still present |
| --- | --- |
| Local CLI, SQLite jobs, call accounting and owner decisions | No city interface, authenticated service or durable background worker |
| Configurable roles, models, profiles, paths and bounds | No comparative evaluation of full research quality across backends |
| Codex question-driven source planning | Source discovery originally required Codex; September 18 foundation adds explicit shared-tool search configuration |
| Public HTTPS collection, DNS checks, PDF extraction, archived evidence | No general shared agent-tool loop, licensed market feed or comprehensive coverage guarantee |
| Exact excerpt selection and independent review calls | Not yet a collaborative team with persistent notes and adaptive delegation |
| Source-coverage gate, semantic diagnostics and bounded repair | No general reconciliation/resume UI or automatic resolution of uncertain calls |
| Standalone scenario arithmetic | No company-data extraction/normalization and reproducible research computation pipeline |
| 136 tests plus formatting, lint, typing, build and dependency audit recorded | Those checks do not constitute a live research-quality evaluation |

The recent remediation used simulated model/HTTP responses; no live subscription run was made for that change. Earlier live checks are historical and are documented in [verification](verification.md).

## 3. Owner workflows

F-01 Assign work: accept a natural-language question, constraints, preferred execution location, profile and resource limits. Clarify material ambiguity or disclose a reasonable representative scope. Persist the resolved request and configuration.

F-02 Inspect work: show assignments, current step, evidence, actual usage, remaining allowance and unresolved blockers. Never equate an agent's narrative with completed work.

F-03 Review results: show a versioned report with supporting sources, reproduced calculations, uncertainties, opposing evidence and independent review results. Acceptance remains a separate owner decision.

F-04 Continue safely: an owner can request a follow-up, supply sources, revise scope or dispatch repair with lineage. Pause/cancel/resume semantics must preserve completed work and unknown external outcomes; do not replay uncertain requests automatically.

## 4. Research-team capabilities

F-05 Shared tools: a typed registry exposes search, fetch, archive read, table/data retrieval, sandboxed calculation and note/task operations. Direct connectors and MCP can both implement the contract. Models choose tools; Esperia validates arguments, checks permissions, enforces budgets, executes and records results.

F-06 Investigation loop: scope → hypotheses → evidence collection → analysis → comparison/challenge → targeted follow-up → report/review. The lead may revise its plan when new evidence appears. Stop when defined evidence criteria are met, marginal research adds little, required evidence is unavailable or resource limits are reached. A configurable loop bound remains mandatory.

F-07 Hypothesis register: record the claim being tested, expected evidence, disconfirming evidence, test method and outcome. Distinguish observed facts, derived results, assumptions and speculation. Preserve rejected hypotheses with reasons.

F-08 Reproducible quantitative work: retain source values, dates, units, currencies, period mappings, transformations, code/version, parameters and outputs. For historical tests, use point-in-time information and explicitly address survivorship, look-ahead, multiple testing and transaction costs where applicable. Do not imply backtesting exists merely because a model narrates one.

F-09 Scoped memory: store dated, source-linked research notes and reusable methods under city/project/agent scopes. Memory is evidence with freshness and permissions, not unquestioned truth. Corrections supersede earlier claims without erasing history.

F-10 Evaluation: measure source relevance, factual/citation support, numerical reproducibility, conflict detection, completion quality, resource use and recurring errors. Pin evaluation datasets and instruction/model versions. Software test success and research-quality scores are separate release gates.

## 5. Roles and collaboration

Roles are configurable assignments, not a fixed count of agents or separate mandatory services.

| Role | Responsibility | Required work product |
| --- | --- | --- |
| Mayor/research lead | Scope, decomposition, allocation, synthesis and escalation | Versioned plan, task ownership and stopping rationale |
| Research specialist | Independently investigate a bounded topic | Evidence-backed notes and unanswered questions |
| Quantitative analyst | Normalize inputs and test relationships | Reproducible calculation/experiment package |
| Skeptical reviewer | Seek counterevidence and challenge support | Specific verdicts and unresolved objections |
| Research editor | Make conclusions understandable and traceable | Report with citations, assumptions and dissent |
| Operations role | Explain waits, failures and budget state | Actionable operational status; no self-granted authority |

F-11 Shared notebook entries contain: author/role; task and hypothesis IDs; claim type; exact evidence references; data-as-of date; assumptions; opposing evidence; confidence rationale; next suggested test; visibility scope; revision history.

F-12 Compare notes after initial independent investigation to reduce anchoring. Cross-agent requests become owned tasks rather than unbounded chat. Mark duplicate sources; multiple agents citing one issuer announcement do not count as independent corroboration. Preserve disagreement instead of averaging votes into confidence.

F-13 Insights emerge from explicit connections between findings. A proposed causal explanation becomes a new hypothesis with a validation task. It is not promoted to a fact because several agents repeat it.

## 6. Quant example, not a fixed workflow

For an energy-growth question, the lead could select representative business categories and assign demand, company economics, infrastructure constraints and downside investigations. The team might connect demand growth with financing or grid constraints, then test which business exposures actually benefit. The scope and horizon come from the request; company names and research branches are not embedded in application code.

A nonfinancial science question should use the same tool/notebook framework with a different explicit profile and appropriate checks.

## 7. Execution and reliability

F-14 Persist jobs, plans, role assignments, tool calls, notes, review outcomes and events. Work leases/heartbeats prevent duplicate ownership; idempotency protects actions; timeouts become durable outcomes. Resume must distinguish safe reads from uncertain external effects.

F-15 Closing a browser must not stop work on an active worker. Closing/sleeping the only machine running Ollama does stop local inference; an unattended promise requires an always-on authorized worker and reachable selected model. Prove restart, disconnect and provider-limit recovery rather than relying on the city animation.

F-16 Separate inference-call, tool-call, runtime, concurrency, output and monetary limits. Reserve enough capacity for review. Show what a limit actually measures. Idle avatars and ordinary state updates make no model calls.

F-17 Notify only meaningful completion, failure, material new evidence or required owner action on configured channels. Deduplicate events; preserve quiet hours/preferences. Notification delivery and external messages require the applicable owner authorization.

## 8. Permissions and trust

- External content is untrusted data and cannot grant permissions or alter the task's acceptance rules.
- Tools have scoped capability grants; role or model changes do not silently increase access.
- Read-only research, controlled local calculations and note creation may run within the approved task envelope.
- Research acceptance does not authorize trades, transfers, purchases, external messages or infrastructure changes.
- Private portfolio material, secret management and brokerage connectors remain outside the public-research pilot until their own storage/access controls are implemented.
- Runtime-generated code needs isolation from coordinator credentials and state before execution is exposed to agents.
- Reviewer checks must be bound to the applicable report/evidence version. Agents cannot weaken their own checks to claim completion.

## 9. Additional proposals, prioritized

Must for the research-team pilot: local-model tool use, durable notebook, clear delegation, independent challenge, traceable sources, bounded iteration and an evaluation set.

Must for the first usable city: browsable Library with discipline collections and document viewing. Should for the city beta: contradiction view, calculation inspection, live office/job panels, pause/recovery controls, meaningful notifications and an approved always-on option.

Could follow later: saved research watchlists with thesis-change alerts, reusable department templates, read-only portfolio imports, interactive scenario exploration and personalized city decoration.

Deferred: autonomous trading, self-approved purchases, autonomous permission expansion, model-weight training, a general app-building division, and elaborate social simulation without a work-related purpose.

## 10. Pilot acceptance scenarios

A. Ollama-only inference answers a new-topic research request using an explicitly configured search tool; no cloud language-model call occurs.
B. Two specialists investigate separate questions, compare evidence and record a real disagreement that changes or qualifies the report.
C. A calculation can be rerun from archived inputs; changing an input invalidates dependent results/review.
D. Missing evidence or an invented citation stays blocked with an actionable task; agents cannot talk it into accepted status.
E. The owner can inspect actual work in City Hall, the research building and Library, open an archived public document from its discipline collection, override a delegated decision and inspect an agent after a model change; closing the browser leaves an active worker running.
F. A worker restart or network failure neither duplicates work nor discards uncertainty.

A–D gate the research-team pilot. E gates the usable city. F plus deployment/restore checks gate unattended beta.

## 11. Longer-term city breadth

The owner is exploring agents across many disciplines, but has not committed to representing every real-world city profession. Treat the city as an extensible home for useful specialties. Departments should emerge from actual owner goals and supported capabilities rather than a fixed exhaustive roster.

Architecture agents creating distinctive buildings are an expressed future interest. The owner confirmed their scope: designing Esperia’s in-city buildings. Proposed in-city workflow: design brief → building proposal/preview → owner review → versioned city asset. This is a planning proposal, not an implemented generator or authorization for automatic city expansion.

The first usable release remains the research team and a simple live city. Additional disciplines need their own inputs, tools, artifacts, evaluation criteria and effort estimates before entering the active roadmap.

## 12. Confirmed owner governance and identity

F-18 The owner finances Esperia and has final authority over financing, major expansion and strategic commitments. The mayor may delegate, sequence tasks and choose research methods within an owner-approved assignment and resource envelope. Approval of an envelope permits its bounded consumption, not new financial commitments. A proposed cluster of medical research bays, substantial agent growth, a new paid service or an increased allowance needs a concrete owner decision before execution. Expansion proposals include purpose, agent/capability changes, resources, recurring and one-time costs, limits and alternatives. Approval binds the proposal version; material changes require a new decision.

F-19 The owner can override mayor decisions, reprioritize, reassign or stop work. Persist who changed what and when; invalidate conflicting queued actions and pause active work at a safe boundary. Explain any already-completed external action that cannot be undone. Overrides do not fabricate evidence or retroactively change historical outcomes.

F-20 Agent identity survives model changes: stable agent ID, name, specialty, history, permitted memory and evaluated methods remain attached to the agent. Record the model/configuration used for each run; changing a model neither resets history nor grants permissions. Validate capability compatibility before dispatch.

## 13. Library as a usable knowledge base

F-21 First-release places are City Hall, one research building and the Library. Each research discipline gets a labeled rack or room in the Library, with accessible equivalent navigation. Disciplines come from configured/current research work rather than a hardcoded list. Cross-disciplinary documents can appear in multiple collections while referring to one versioned artifact.

F-22 Library entries open actual documents and files, at minimum the collected public-source materials, rather than only generated summaries. Provide readable text/HTML, PDF viewing and a safe file download/original-source link for formats without an embedded viewer. Show title, discipline, source, date, collection time, version and references from research notes/reports. Preserve archived and current-source distinctions. Unavailable files show an honest reason. Render external content without executing active scripts.

F-23 “Public sources” describes the material, not permission to publish the whole Library on the public internet. The initial owner-facing Library retains access controls; private materials remain restricted. Any later public visitor portal requires an explicit publishing/access decision.

## 14. Research outcomes and the future economy

The owner wants research teams judged by the money their research makes. Record attributable financial outcomes when they exist, with the originating research/report version, decision/action, observation period, costs and attribution limitations. Distinguish realized revenue/profit, unrealized value, simulated results and estimates. No outcome yet means unmeasured, not an invented score. Performance reporting does not authorize real trading or spending.

Proposed evaluation design: financial outcomes lead the quant-team business scoreboard, alongside risk/exposure, capital used, costs and evidence quality so teams cannot win simply by taking more risk or claiming others' returns. Research in other disciplines retains appropriate outcome measures when money cannot yet be attributed. Better observed results can inform owner-reviewed method/resource changes; they do not automatically train model weights or expand authority.

Competing strategy teams, reputation and agents investing in a quant company are future ideas outside the first release. The owner confirmed an internal simulated economy: agents may eventually invest simulated currency in in-city quant companies. Define allocation, settlement and anti-gaming rules before implementation; simulated holdings confer no claim on real money or authority to spend it. Internal currency, reputation and actual money must have separate records; no automatic conversion or authority is implied.

A future University can teach reusable methods through practice tasks and evaluated instruction changes. Preserve failed experiments and lessons in the Library. Competition and critique use independent evaluation; calling the workflow a GAN does not make it a model-training system.


## 15. Universal Library graph — owner direction September 21, 2026

F-24 The Library is one city-wide knowledge graph, with an Obsidian-like global view and focused local views. Disciplines, teams, subjects and projects are overlapping collections of the same nodes. Rooms/racks organize navigation; they do not isolate knowledge or duplicate shared documents. The first backend supports exact-label collections; hierarchical collection navigation is a later interface concern.

F-25 Findings, hypotheses, questions, source documents, methods and other author-defined note kinds retain stable identity and append-only revisions. Relationships record their author, rationale, visibility and both compared revisions. Support and disagreement are explicit links, not automatic promotion to truth. Editing a note marks earlier revision-bound relationships stale until reconsidered.

F-26 A global or filtered view must not expose restricted notes, relationship rationales, hidden endpoint identities or hidden collection membership. Initial graph commands are local owner operations with a narrowed public projection; authenticated agent grants and network API permissions remain separate acceptance work. Scope changes need an explicit publishing workflow, not an ordinary content edit.

F-27 The Library supports text search, backlinks across collections, source provenance and historical note inspection. Graph pagination/truncation must be visible to clients. The full interactive graph, raw file/PDF viewing, semantic search and automatic suggested connections are not implied by delivery of the notebook data model.


## 16. Owner research guide and accuracy — September 21, 2026

F-28 Provide a question-framing assistant for the owner. It helps clarify purpose, audience, ambiguous terms, time horizon and meaningful comparisons, suggests subquestions, identifies assumptions/premises requiring verification, and proposes evidence and success criteria. It preserves owner intent and does not silently decide unanswered scope choices. It may ask up to three prioritized questions per response; later UI can present these conversationally.

F-29 Question-preparation sessions belong to the owner's Library as versioned research briefs. The configured guide identity and note ID survive model changes. Each explicit owner message permits one bounded model call. Continuing a brief retains the original question, accumulated clarifications and initial time anchor; concurrent edits cannot overwrite one another. The current local CLI provides the first interaction surface; city UI and authenticated identity/grants remain pending.

F-30 Accuracy is imperative. A material factual, numerical, date, unit or attribution error fails research acceptance irrespective of presentation quality. Exact citation matching alone is insufficient. Missing evidence, uncertainty, contradictions, forecasts and assumptions must be represented honestly. A prepared question is neither an accepted research result nor authority to dispatch a research team.
