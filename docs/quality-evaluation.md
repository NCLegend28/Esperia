# Finishing research quality evaluation

Engineering checks and acceptable research are separate gates. The 241-test pre-notebook baseline passed, but the local energy study and repair left material gaps. Changing schemas made outputs structurally valid; it did not prove sound research.

## What the owner needs to do

1. Supply two or three representative questions and describe the decision or useful output expected from each. The existing energy comparison and coral-restoration questions remain development examples.
2. The owner approved the rubric in `config/evaluations/research-quality-v1.json`: zero material unsupported claims or numbers; zero fabricated accepted quotes or permission/budget violations; at least 90% relevant sources; at least 4/5 on every human quality dimension. Accuracy is now an explicit hard gate: any material factual/numerical error, wrong date/unit/entity attribution, or unresolved material contradiction presented as fact fails the case regardless of other scores. This approval is recorded; do not ask the owner to approve the same rubric again.
3. Approve the final held-out questions and run allowance before freezing the test. The proposed 4 cases × 2 repeats × 2 backends × 12 maximum calls is an upper ceiling of 192 calls, not currently authorized spending. Smaller batches can be approved first. No new paid API, model download or provider subscription is implied.
4. Review the blinded outputs and supporting evidence, then accept the gate or record concrete failures. A researcher's model cannot be its sole judge.

The owner authorized local Qwen versus the existing Codex subscription backend. A development comparison may reuse the same verified energy archive with two analysis/review calls per backend. That isolates writing/review differences; it does not evaluate source search, represent a held-out test, or establish broad model superiority.

## Build work

Prepare frozen question/answerability criteria, representative and deliberately difficult cases, versioned prompts/config/model identities, scoring sheets and an audit of material claims and calculations. Run each approved batch inside its cap. Preserve original responses, source hashes, provenance, failures, token/call use and elapsed time. Record source availability/date differences for end-to-end comparisons. Compare blindly where practical.

Answerable cases need useful supported conclusions. For genuinely unanswerable cases, the correct result is a specific justified blocker, not invented evidence. Report both completion and truthful blocking; do not raise the completion score by excluding failed runs after seeing results. Four cases and two repetitions remain a small pilot, not a reliability guarantee.

Evaluation is finished only after approved criteria are frozen, held-out results are recorded, a human checks source/claim support and numerical validity, and the owner accepts the result or the gate is explicitly failed. Training or replacing a model comes after locating whether failures arise in retrieval, planning, attribution, reasoning or formatting.


## Owner inputs received

- Comparison of local Qwen and the existing Codex subscription backend is authorized, with bounded calls and no paid API fallback.
- “What factors in the cybersecurity space dictate consumer trust?” is an owner-supplied candidate. Define buyer scope and expected output before freezing it.
- The owner clarified the second question as investing or trading: “How do traditional investing or trading strategies compare with modern ones?” Define representative approaches and comparison criteria before freezing it.
- Rubric approval is complete, with accuracy imperative. Final held-out case selection, full-batch resource allowance and final human scoring remain pending. No additional candidate has been used to tune prompts.


## Development comparison — September 21, 2026

Same two archived energy sources and question, with two calls per backend and no revision loop. This only tested analysis/review on known development evidence; no retrieval comparison, human quality score or held-out acceptance was performed.

| Backend | Observed outcome | Elapsed |
| --- | --- | --- |
| ollama | Generated preliminary report; job blocked by research gates | 274.14 seconds |
| codex | Analysis persisted; reviewer dispatch failed with uncertain call outcome; no report | 41.97 seconds |

Artifacts: `.local/dev/evaluations/notebook-quality-development/comparison.json` and the per-backend job directories. Codex's failure was not diagnosed beyond the adapter stopping; do not infer a model quality score or retry an uncertain call automatically. The subscription review path requires diagnosis before the final evaluation batch. No winner is established by this development comparison.


## Accuracy requirement approved by the owner

Audit factual correctness, not just citation presence. Verify original context, dates, units, arithmetic, denominators, entity attribution, and the distinction between correlation and causation. Sources can be mistaken or misleading, and exact quotations can be applied incorrectly. Material contradictions must be addressed. Forecasts must remain forecasts with assumptions and limitations; unavailable facts must be disclosed rather than guessed. A human accuracy audit remains mandatory before acceptance.

The research-question assistant helps define an answerable question, identify ambiguous terms and assumptions, and propose how its answer will be verified. Its brief is preparation, not evidence, a finding, or permission to start a research job. See `docs/question-assistant.md`.
