# Verified handoff and date correction — September 21, 2026

Owner job `31adf286-bbbf-47d0-8cfc-af4267bc3542` gathered two documents but did not generate a report. Its final decision selected search-result IDs `R1`/`R4` instead of verified-source IDs `S1`/`S4`; the application rejected that handoff after its decision budget was spent. It also searched for 2023–2028 despite a current five-year request.

## Changes

- The model's finish schema now enumerates only successfully read source IDs. With no verified sources, finish is unavailable. The application separately enforces source membership, uniqueness and configured source limits; archive integrity checks remain mandatory.
- A UTC job-start date and temporal guidance are saved in the request and carried into every investigation decision and the evidence handoff consumed by analysis/review.
- Unambiguous “next/coming N years” receives calendar start/end dates derived from that saved date. Numeric values and English one–ten are supported. Explicit dates and multiple horizons are preserved for interpretation rather than silently replaced. Other temporal phrasing receives the date anchor without claiming a resolved range. Leap days are handled by calendar arithmetic.
- Resuming a new job preserves its original timeframe. Older resumable/library jobs without temporal context acquire and save an anchor on their next invocation. The failed owner job was not reopened or edited.

No model, tool or decision budget was increased. No visual/UI files or CLI interfaces changed. The existing `investigate` command uses these corrections for new runs. This is temporal guidance, not a guarantee of publication freshness or factual correctness: older documents remain usable as historical context, and report review must still identify insufficient current evidence.

## Verification

Targeted live Qwen checks used only two local model calls and no new web requests:

1. A fresh first decision proposed `energy companies growth potential 2026-2031`, using a saved anchor of 2026-09-21 and end date 2031-09-21. It paused before executing the search.
2. A copy of the failed job's pre-handoff history and archives successfully finished with `S1` and `S4` on its last decision. It did not generate a report or modify the original job.

Artifacts: `.local/dev/verification/handoff-date-a5c40888-e3fa-4f0d-8c61-487247812cd3`.

Regression tests cover the exact wrong-ID failure, unknown/duplicate IDs, no-evidence finish, cross-topic dates, explicit historical dates, multiple horizons, leap dates and temporal persistence through report resume. Full research quality and live cloud parity are not established by these focused checks.

Software verification: 221 tests passed, with Ruff and strict Mypy passing.
