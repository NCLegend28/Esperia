# Adaptive execution framework

Delivered September 20, 2026. This is a single-worker execution foundation. Collaborative teams, a shared research notebook and the city remain separate roadmap work.

## Run and control

With the configured Esperia SearXNG service and an installed Ollama model:

```sh
uv run esperia investigate "Compare energy companies and their potential for growth over the next 5 years." --backend ollama
uv run esperia agent JOB_ID
uv run esperia agent JOB_ID --action pause
uv run esperia agent JOB_ID --action resume
uv run esperia agent JOB_ID --action stop
uv run esperia review JOB_ID
```

Replace `JOB_ID` with the printed identifier. Controls are trusted local-owner commands, not agent tools. Use another terminal to pause or stop active work. Resume executes in the foreground and uses the original saved settings and remaining job budget. The process must stay running; this is not an unattended worker service.

`investigate` accepts `--backend`, `--mode economy|deep`, `--profile` and `--max-calls`. It always uses the configured shared search service, including with Codex; it does not silently fall back to cloud search. The existing `research` command retains its current behavior.

## What loops, and what stays fixed

1. Give the worker a goal, profile criteria, granted tools, observations and remaining allowance.
2. The selected model chooses search, read, finish, or blocked.
3. The application validates the action, records it, executes a granted operation, and saves its result.
4. The next decision sees the new evidence and can change the investigation direction.
5. Finish requires successfully read, integrity-checked archives. It hands evidence to the existing analysis/review workflow; it cannot approve a report.

Generation schemas expose only actions available within the remaining resource bounds. The last decision allows finish or blocked. The application still checks budgets, observed IDs, archive integrity and report acceptance independently.

Search snippets are unverified discovery metadata. Document reads use observed result IDs, not arbitrary URLs or filesystem paths. Only unread result IDs are offered in the generation schema, with an independent application check before dispatch. After an exact duplicate tool action, the next decision temporarily excludes that tool when another useful tool is available. Search remains available again after a fresh observation. Each read makes one bounded retrieval using existing public-network and PDF/extraction protections. A redirect or inaccessible document returns an unavailable observation; the model can search for another source. Raw content and selected passages remain archived, and omitted context is disclosed. Reads do not automatically crawl linked pages.

An agent loop is useful where evidence determines the next step. It does not replace deterministic validation, source integrity, usage accounting or owner decisions. Report analysis/review remain fixed bounded stages after the adaptive investigation; automatically delegating follow-ups between independent researchers is still future work.

## Configuration

Choices are centralized in validated settings. These defaults can be overridden in `esperia.json`:

```json
{
  "agent": {
    "steps": 10,
    "seconds": 1800,
    "repeated_actions": 2,
    "read_calls": 4,
    "observation_chars": 4000
  }
}
```

- `steps`: maximum investigation model decisions, including the final handoff/blocker.
- `seconds`: active investigation time across resumptions. Checked at boundaries; an already-running call retains its provider/network timeout. It excludes report generation and time spent paused.
- `repeated_actions`: maximum duplicate completed tool actions before the framework stops for lack of progress. Duplicate actions reuse earlier observations and do not call the tool again. This counts consecutive duplicate actions. A fresh observation resets the stall count; the overall decision cap still applies.
- `read_calls`: document-read allowance, further bounded by `requests` and `documents`.
- `observation_chars`: document text exposed in each investigation observation. The report receives the separately verified archive projection.

`search.max_calls` remains a separate search allowance. `source_tokens`, provider timeouts, prompt size and source policies still apply. The overall model cap reserves mandatory report/review capacity before investigation: `agent.steps + 2` for economy, or `agent.steps + min(agent.read_calls, documents, requests, max_seeds) + 3` for deep. Default economy allowance is 12 calls. Actual early completion may use fewer. An explicit cap is never silently increased; insufficient capacity fails before a model is constructed. Optional revisions use only the remaining overall allowance.

## Checkpoints, pauses and recovery

Each adaptive job stores `agent.sqlite`, `tool-calls.sqlite`, model responses, original configuration, individual `reads/R…` archives and the final `evidence` archive. SQLite transactions reserve actions; a process lock prevents two workers from driving the same run. The journal is authoritative for paused/stopped execution; the job ledger retains accounting and report status.

Pause/stop are cooperative: an in-flight call can finish, and control takes effect before the next dispatch or final report registration. Completed decisions and observations are saved. A paused completed decision resumes without regenerating it. During reporting, completed stages are reused only when their full input fingerprint matches, calls are settled, and schema/content checks still pass. A report already registered before a process interruption is recovered without regenerating it.

Unknown external outcomes are not replayed. Pending investigation calls, unsettled model calls, failures, changed checkpoint inputs or tampered/stale archives prevent continuation. Explicit resume does not erase those conditions or replenish budgets. Inspect the artifacts and use a new bounded job or the existing repair workflow after addressing the cause. There is no automated billing reconciliation or distributed worker lease system yet.

Terminal outcomes include completed execution, a worker-reported blocker, repetition, exhausted time/decisions, owner stop, or execution failure. Completed execution is distinct from passed review or owner acceptance; a completed run may produce a preliminary report with failed checks.

## Verification

Verification: 202 tests passed; Ruff, Black and strict Mypy passed. No dependency changes were needed.

Deterministic tests cover goal-dependent actions across topics, read failure followed by a different search, invented IDs, tampered evidence, separate tool caps, reserved report capacity, no duplicate tool dispatch, concurrent-worker exclusion, time/step limits, interrupted calls, controls, economy/deep checkpoint recovery, revision preservation and report gates.

A live Qwen 2.5 7B probe searched and read a real page, then repeated its search on the final decision. The duplicate was not dispatched and the step cap stopped the run. That led to schema-level final-turn restrictions. The next fresh probe completed search → document read → verified handoff within three local model calls, one search and one read:

- Initial bounded stop: `.local/dev/verification/adaptive-loop-00bc9705-524f-4d64-83bd-b83f3bb29d09`.
- Verified handoff: `.local/dev/verification/adaptive-loop-a836f0f9-f678-4ebb-b392-696f2849d6d3`.

These probes did not generate a report or establish research quality. Live cloud parity and representative end-to-end research benchmarks remain pending. No new model was selected, downloaded or trained.


## Repetition recovery correction

Owner job `e9549ef3-444f-4c88-a508-ca1115556698` used the default three-search allowance. It made three model decisions requesting one identical query, executed one search, then stopped at the repetition guard without reading any documents. The original one-search live probe did not expose this default-allowance behavior.

The correction supplies explicit duplicate-action feedback, temporarily removes the repeated tool from the next generation schema when an alternative is available, offers only unread document IDs, and independently validates those IDs before dispatch. Consecutive stalls still stop; fresh observations reset that counter. Call, time, source and review budgets are unchanged. The original blocked job remains intact and is not automatically resumed.


Verification after the correction: **207 tests passed**, with Ruff, Black and strict Mypy passing. A fresh Qwen 2.5 7B investigation used the owner's normal search/decision/read limits (3/10/4), with a shorter diagnostic provider timeout of 180 seconds. It completed a verified handoff in 10 model decisions: one actual search, four suppressed duplicate search requests, four document reads (two usable, two unavailable), and a final selection of `S1` and `S4`. Artifact directory: `.local/dev/verification/repetition-recovery-153acaac-2cdf-46e0-a3c8-8d6f21a639b5`.

This demonstrates recovery from the reported stall, not strong model planning: Qwen continued requesting the same query between reads. The diagnostic generated no report and does not establish research quality. Run a fresh `investigate` job to use the correction; the prior terminal blocked job is not reopened.
