# Library notebook and universal graph

The Library is one knowledge graph. Discipline rooms, project shelves and team collections are views into shared nodes. One document may belong to energy, economics and ecology without becoming three separate documents. Explicit links carry support, contradiction, related ideas or other author-defined relationships across collections.

Implemented now: a reusable SQLite repository (`notebook.py`) and local owner CLI (`library`). Data lives at the selected environment's `data_root/library.sqlite`. No model calls are needed. Node identity survives content revisions; author IDs are attribution strings pending the agent identity registry. Model names are not identities.

## Create and revise notes

Save a JSON note such as:

```json
{
  "title": "Does electricity demand change this growth hypothesis?",
  "body": "A proposed relationship to investigate, not an accepted conclusion.",
  "kind": "hypothesis",
  "author_id": "owner",
  "role": "researcher",
  "scope": "owner",
  "collections": ["energy", "economics"],
  "assumptions": ["The forecast applies to the selected period."],
  "counterevidence": [],
  "confidence_rationale": "Unverified; needs dated primary evidence.",
  "next_test": "Compare the hypothesis against issuer disclosures."
}
```

```sh
uv run esperia library add note.json
uv run esperia library show NODE_ID
uv run esperia library revise NODE_ID revised-note.json --expected-revision 1
uv run esperia library show NODE_ID --revision 1
uv run esperia library graph
uv run esperia library graph --collection energy --query demand
uv run esperia library links NODE_ID
```

Notes additionally support task/hypothesis IDs, an as-of date, exact evidence reference metadata, assumptions and counterevidence. Manually supplied references are assertions, not mechanically verified citations. A notebook entry never approves a research report. Conflicting edits fail instead of overwriting history.

## Connect ideas

`library link link.json` accepts `source_id`, `source_revision`, `target_id`, `target_revision`, `relation`, `rationale`, `author_id` and optional `scope` (default `owner`). Both endpoints must be current when the connection is made. Later edits preserve the connection but mark it stale. Incoming/outgoing `links` pages cross collection boundaries. Relation names are data; the system does not infer truth from agreement or connectivity.

## Import actual evidence

```sh
uv run esperia library import-archive /absolute/path/to/job/evidence \
  --author owner --role librarian --collection energy --collection economics
```

Import verifies archive freshness, raw snapshot hashes and extracted passages before writing. It stores readable extracted text and URL/hash provenance. Repeat imports reuse the same document node; new collection memberships append a revision. Incompatible projection text or scope raises a conflict. An imported document's as-of date is its retrieval date and is explicitly labeled as such, not its publication date. Raw files remain in the research archive; a future document catalog/viewer will serve them safely. Importing a PDF currently exposes its archived extracted text, not an embedded PDF viewer.

## Views and boundaries

`--public` on `graph`, `show` or `links` narrows results to public nodes; public relationships also require public endpoints. Private relationship rationales remain hidden even between public documents. Scope is fixed across ordinary revisions; publication needs a separate future workflow. This flag does not publish a site or authenticate a remote caller.

Graph output is versioned JSON with nodes, revision-bound edges, staleness and pagination metadata. `next_after` pages nodes; graph edges are only those between the page's nodes. `edges_truncated` explicitly signals the edge cap; use `links NODE_ID` for separately paginated cross-page relationships. Page size, edge cap and input byte limits are owner-configurable through `notebook_page_size`, `notebook_edge_limit`, and `notebook_input_bytes`.

Still pending: authenticated agent identities/grants, automatic research-note writes, a hypothesis/assignment lifecycle, full Obsidian-style interactive graph, semantic search, suggested links, raw file/PDF viewing, API/event delivery and safe publication. No visual files are changed by this backend work.
