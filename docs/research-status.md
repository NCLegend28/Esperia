# Esperia implementation status — September 20, 2026

Esperia is a working command-line research foundation, not yet the research-team city described in the product specifications. Passing engineering checks does not establish report quality.

## Implemented

- Research jobs, saved artifacts, model-call accounting and version-bound owner decisions.
- Codex, Ollama, llama.cpp and hybrid inference adapters; configurable model and research settings.
- Separate local SearXNG instance, provider-neutral search tool and bounded local-model source selection using observed result IDs.
- Typed tool contracts, explicit grants, persisted call reservations and resource limits.
- Adaptive `investigate` execution: search/read/replan, verified archive handoff, pause/stop, explicit checkpoint resume and reserved report/review capacity. See [execution framework](execution-framework.md).
- Public-source retrieval, archived evidence, citation/excerpt checks, scope checks and separate review stages.
- Appearance, behavior and phased delivery documents. The task backlog records partial progress rather than declaring whole milestones complete.

## Still incomplete

- Reliable, independently evaluated end-to-end local research. The new investigation loop searches and reads adaptively; subsequent analysis/review remain predefined stages.
- Distributed workers and reconciliation of uncertain external outcomes. Local checkpoint recovery and cooperative pause/stop are implemented for adaptive jobs.
- Shared notebooks, hypothesis tracking, independent research-team comparisons and adaptive coordination.
- Stable model-independent agent identities, city interface, Library catalog/document viewer and mayor expansion controls.
- University, competing companies and simulated investment economy.

## Source-action correction

Job `16b09972-d86a-4b88-a5e9-9f4eff9e53a2` returned valid JSON that combined a search request with final source selections. The old application's cross-field validator rejected it, but those constraints were missing from the schema supplied to the model. This is not sufficient evidence that the worker needs fine-tuning.

Search and finish now have separate typed branches inside a decision envelope, so generation receives the mutually exclusive constraints. Rejections include safe field paths and error codes. Repeated identical queries reuse prior observations without another search request; the model-decision budget still applies. Existing failed jobs are preserved and not automatically replayed.

Verification: 175 tests passed; Ruff, Black and strict Mypy passed. A fresh Qwen 2.5 7B source-only diagnostic used two local model calls and one search and produced a valid source plan. Artifacts: `.local/dev/verification/source-loop-4140d487-f7b5-4545-92c1-eef22367573c`. It did not generate or validate a research report. Live Codex parity has not been verified for this change.

A separate bounded full-pipeline baseline, job `28db498e-beec-42b7-bd96-00a23e0be28e`, completed source discovery but timed out during analysis selection at the explicitly configured 180-second diagnostic limit. Artifacts: `.local/dev/verification/baseline-energy-20260918/research/28db498e-beec-42b7-bd96-00a23e0be28e`. This is not evidence that the normal 900-second setting always fails. The outcome remains unresolved and was not automatically replayed.

## Next delivery sequence

1. Complete representative energy and nonfinancial baseline evaluations: relevance, evidence support, completion, latency and resource use.
2. Extend the delivered single-worker retrieval/checkpoint foundation with shared notebooks and model-independent agent identities.
3. Build the multi-worker adaptive coordinator: receive a goal and acceptance criteria, choose an action, inspect evidence, revise the plan, and stop with a verified result or explicit blocker. The model chooses intermediate steps within granted tools and budgets.
4. Compare candidate worker models on the same cases before changing defaults. Address recurring instruction/tool issues before considering fine-tuning.
5. Connect accepted research workflows to City Hall, the research building and the discipline Library.

See [TASKS.md](../TASKS.md) for dependencies and acceptance gates. No calendar deadline has been set.

## Execution framework update

The single-worker adaptive path is now implemented and documented in [execution framework](execution-framework.md), including a successful live three-decision search/read/handoff probe. This does not mark the full collaborative-team or unattended-worker milestones complete.
