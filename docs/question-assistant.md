# Research-question assistant

The research guide helps turn an idea into an answerable question. It proposes scope and subquestions, asks prioritized clarifications, identifies assumptions and factual premises, and specifies evidence and accuracy checks. It does not answer the underlying research question, search the web, or start research automatically.

```sh
uv run esperia question "Help me frame a question comparing approaches to a topic" --backend ollama --collection my-discipline
uv run esperia question "Here is my clarification" --continue NOTE_ID --backend ollama
uv run esperia library show NOTE_ID
uv run esperia library show NOTE_ID --revision 1
```

Each response includes the Library `node_id`, revision, preparation job ID and structured brief. Use the same `node_id` to continue, even after changing the backend/model. Author identity comes from `question_assistant_id`; it is distinct from per-call model identity. Changing the configured guide ID represents a different guide and does not silently take over existing briefs.

The brief remains private (`owner` scope) and unverified. `ready_for_owner_review` means it has no remaining clarifying questions and is ready for the owner to assess; it does not approve research or claim correctness. The owner can edit the proposal, supply another clarification, or explicitly submit the refined question through `investigate` when ready. No shell command is generated or executed from the model's output.

Configurable choices:

- `question_assistant_id`: persistent guide attribution (default `research-guide`).
- `question_instructions`: owner-adjustable question-framing guidance.
- `question_turn_limit`: maximum initial message plus clarifications in one brief (default 8).
- `question_brief_tokens`: requested output bound (default 1800; advisory for the subscription CLI).
- `planner_model`: model role for framing; the local adapter uses its configured installed model.
- Existing input/context bounds, provider timeouts and backend settings still apply.

Each owner message creates a one-call preparation job with saved request, resolved configuration and response. Malformed outputs and uncertain calls stop without automatic retry. Optimistic notebook revisions prevent concurrent messages from overwriting one another; a conflicting generated response remains in its job artifacts for inspection. Preparation jobs use `completed` state after a settled framing call and do not register research reports or become eligible for report acceptance.

This delivers the CLI and durable notebook foundation. Authenticated agent identity/grants and an in-city conversational panel are later integration work. Factual verification is performed during research and independent quality evaluation, not by this preparation assistant.
