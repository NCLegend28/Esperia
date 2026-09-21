# Esperia delivery roadmap

Version 0.1 · September 17, 2026 · Phase-based plan · Owner confirmed no deadline

The appearance and functional specifications are separate: [what it looks like](appearance-spec.md), [how it works](functional-spec.md). [TASKS](../TASKS.md) is the concrete work queue. The [original build spec](build-spec.md) preserves concept history; this roadmap does not claim the proposed features exist.

## Delivery assumptions

- The owner confirmed **no deadline**. There are no committed start, launch or milestone dates, and weekly capacity has not been assumed.
- 260 estimated focused delivery hours, including verification and review preparation, across one implementation lane. Allow approximately 20–25% additional contingency: a provisional planning range of **312–325 hours**. These are effort estimates, not elapsed-time promises; revise after the local-tool pilot.
- The owner selected a working research team with a simple, live city view for the first usable release. M3 proves the research team; M4 combines it with the simple city. Unattended operation follows. Detailed visual polish is deferred.
- No new subscription, search provider, cloud resource or notification channel is authorized by this plan. Existing subscription-only model execution remains the policy; no silent API-credit fallback.
- Work proceeds when dispatched. Complete the acceptance gate before advancing; owner review and unresolved dependencies may add elapsed time.

## Phases and completion gates

| Gate | Phase | Tasks | Estimated effort | Exit condition |
| --- | --- | --- | ---: | --- |
| M0 | Definition and baseline | E-01–03 | 12h | Scope, evaluation gates, visual direction/reference decisions and baseline documented |
| M1 | Shared tools and local inference | E-04–07 | 40h | Local model can research a fresh topic with validated search/retrieval tools; no cloud language-model dependency |
| M2 | Collaborative investigation | E-08–11, E-25 | 48h | Owned tasks, persistent notes, independent findings, disagreement and bounded follow-up work end to end |
| M3 | Research-team pilot | E-12–14 | 28h | Reproducible quantitative evidence and independent review; functional acceptance scenarios A–D pass |
| M4 | Usable live city | E-15–19, E-26–27 | 80h | Owner can assign/inspect/review real work in city and accessible panels; visual blueprint approved |
| M5 | Unattended readiness | E-20–23 | 40h | Recovery, authorized always-on execution, restore and notification checks pass |
| M6 | Unattended beta | E-24 | 12h | Held-out evaluation and owner acceptance; browser disconnect/restart evidence recorded |

M2 is a team-workflow milestone, not the full research-quality pilot. M3 includes the calculation and quality gates. Local research and the city may ship independently if always-on hosting is unresolved; do not label that state unattended beta.

The sequence is the timeline: definition → shared tools → collaboration → evaluated research → live city → unattended readiness → beta. Within each phase, follow the task dependencies. Re-estimate remaining effort at each gate without inventing a launch date.

## Critical dependencies

Shared tool contract → configured search/retrieval → local tool loop → collaborative coordinator → evaluated research pilot.

Notebook/task records → authenticated API/events → live city and inspection panels.

Durable workers → authorized reachable runtime/model → restore/recovery evidence → unattended beta.

Existing local Ollama inference depends on its host remaining awake and reachable. An always-on server cannot make a sleeping laptop's model available. Validate the selected subscription/local runtime arrangement before promising unattended work.

## Decisions to settle

| ID | Decision | Proposed assumption | Needed by | Owner |
| --- | --- | --- | --- | --- |
| D-01 | Existing visual reference and required traits | Cities: Skylines-esque but blocky confirmed; collect any additional references | E-02 | Tali |
| D-02 | Art/camera fidelity | Blocky architectural detail; camera/materials pending. Approve reference sheet; simple live city first | E-16 | Tali |
| D-03 | Desktop/mobile priority | Desktop city, accessible narrow-screen panels | E-02 | Tali |
| D-04 | Delivery pace and release priority | No deadline confirmed; proceed by completion gates. Working research team with simple live city confirmed; weekly capacity unspecified | M0 | Tali |
| D-05 | Search/data access | Select a configurable provider after availability/cost check; public dated data suffices for pilot | E-05/E-13 | Tali + build |
| D-06 | Always-on execution and notifications | Review resource quote, model compatibility and channel before commitment | E-21/E-23 | Tali + build |

The original $150 monthly envelope and its allocations are historical planning proposals, not current quotes or spending authorization. Paid provider choices require concrete cost/limit review. If an existing design reference conflicts with a proposed visual detail, preserve the reference and update the draft.

## Evaluation and release gates

E-01 sets explicit numerical thresholds and a frozen representative evaluation set before implementation. At minimum include energy research, a nonfinancial topic, irrelevant-source temptation, conflicting evidence, invalid quotation, missing data, tool injection, exhausted budgets and interrupted execution. Separate deterministic regression tests from live model evaluations, and include held-out cases not used to tune prompts.

Release evidence must report citation support, source relevance, unresolved contradictory claims, reproducible calculations, completion/blocker outcomes, usage and elapsed time. Citation integrity, permission enforcement and truthful blocked states are mandatory; do not loosen them to improve completion rates. A bounded diagnostic/repair flow should explain quotation failures, without converting fabricated text into accepted evidence.

Model quality and tool-use reliability are unknown until measured. If a local model fails the gate, record the limitation and evaluate an explicitly selected alternative; do not silently switch to cloud inference.

## Scope and change control

Must: tool independence, evidence provenance, collaborative notes, reproducible results, bounded execution, independent review and owner control.

First cuts if effort grows: decorative animation, extra buildings, avatar customization and nonessential dashboards. Preserve source/citation checks, isolation, accessibility, recovery and acceptance gates.

Any new capability gets a task, estimate, dependency and acceptance test. Record which milestone or reserve it consumes. Re-estimate after M1 and M3 using measured implementation effort and research quality. Owner review happens at each gate; blocked work retains a specific next action.

## Review checklist at each gate

- What demonstrably works, and where is the evidence?
- What failed or remains uncertain?
- What did it consume versus its allowance?
- Has scope, capacity, provider access or the critical path changed?
- Accept the gate, repair it, or revise the remaining plan explicitly.

## Future direction recorded September 17

Explore architecture agents and additional useful disciplines without requiring a literal agent for every city profession. The owner confirmed architecture agents design Esperia’s in-city buildings. This capability is outside the 260-hour baseline; specify the asset workflow and estimate separately before scheduling. Preserve the confirmed blocky city inspiration in the first simple scene.

## Confirmed governance and first-city decisions

The owner controls financing and major expansion, can override mayor decisions, and permits routine delegation within approved work/resource envelopes. Agent identities persist across model changes. The initial city has City Hall, one research building and a Library with discipline rooms/racks and viewable public-source files. Public-source viewing does not authorize a public internet portal.

E-25–E-27 add 32 hours to the earlier 228-hour estimate: the revised baseline is 260 hours before contingency. M2 and M4 include the new acceptance gates. No deadline is imposed.

Financial outcomes are the owner's desired business measure for research teams. Revenue attribution, competing teams, University teaching, reputation and agents investing in a quant company need separate specifications and estimates. The owner confirmed the investment mechanism is an internal simulated economy. Its currency, investments and returns stay separate from actual money, research revenue and model usage; specifying its rules does not block the public-research foundation.
