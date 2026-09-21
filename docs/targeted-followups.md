# Targeted follow-up research

A completed investigation can still produce a preliminary report. To address its saved gaps with new searches, run:

```sh
uv run esperia repair JOB_ID --search --backend ollama
```

Preview the assignments without making model calls:

```sh
uv run esperia repair JOB_ID --search --backend ollama --plan
```

The configured search endpoint is required. `--search` cannot be combined with `--sources` or `--no-discovery`. Existing repair behavior remains available without `--search`.

## One bounded cycle

The command creates a repair child linked to the parent. It gives the investigator the original question, preserved time horizon, saved assignments, and retained-source metadata. Search queries and document passage selection target those gaps. Newly verified documents are combined with verified parent snapshots, then the analyst receives the previous draft as untrusted context and produces a revision. A separate review invocation evaluates both the configured quality checklist and every assigned repair.

The model-call allowance defaults to `agent.steps + 2`: investigation decisions plus mandatory analysis and review. `--max-calls` can override that allowance within `max_calls`; it cannot consume the two reporting calls during investigation. Search count, document reads, active investigation time, evidence size, and model-call limits remain configurable. No automatic chain of repair children runs after this cycle.

Duplicate dispatch of an unchanged request is refused. Parent reports, source hashes, extracted passages, and archive freshness are checked before use. Changed reports, stale evidence, unresolved parent calls, and undersized budgets block dispatch. Parent artifacts are preserved.

## Evidence and status

The child saves `prior-evidence`, new investigation `evidence`, merged `report-evidence`, `evidence-lineage.json`, `repair-plan.json`, and a bounded `previous-report.json`. New evidence takes precedence when the same URL occurs in both archives. Old-to-new source identities are recorded; old draft citation IDs are never treated as current citations. Whole documents exceeding the combined budget are disclosed in scope limitations. A later search repair can use the child's merged archive.

A registered report may remain blocked when evidence or quality checks fail. Passing automated review only moves it to owner review. Searches and valid citations do not establish that the substantive claims are correct. Missing evidence must remain explicit.

Use the existing `esperia agent CHILD_ID --action pause`, `stop`, and `resume` controls. Completed reporting stages are reused only when their settings, provider identity, inputs, schemas, and ledger state match. Uncertain calls are never automatically replayed.

Legacy follow-ups invented under `repair_reviewer` on a parent with no repair assignments are excluded from new assignments. Genuine missing-evidence and quality-review findings remain.
