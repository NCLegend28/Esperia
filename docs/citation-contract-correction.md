# Archive-bound report citations

The investigation for job `c42a9c64-1f88-426a-a2f0-a2ecaf498734` reached report analysis, but all six sections used excerpt identities (such as `S1:E25`) where source identities were required. Its archive contains `S1`, `S3`, and `S4`; gaps in numbering are valid after unsuccessful reads.

Report generation now receives source choices derived from the actual archive and excerpt choices derived from the generated excerpt catalog. These choices constrain both native structured generation and application validation. The application still resolves exact quotations from the archive and independently verifies citations; it never rewrites an invalid identity into a plausible one.

The shared citation schema applies to economy analysis and revisions, deep evidence selection, and deep drafts and revisions. Model titles, strictness, required fields, and list bounds are preserved. Schemas are isolated per invocation; one job cannot retain another job's citation choices. Schema changes also change the existing stage cache/checkpoint fingerprint.

Regression coverage includes the reported excerpt/source mix-up, invented identities, nonconsecutive archived IDs, empty excerpt catalogs, per-job isolation, and generation schemas for both research modes and their revision calls. Earlier invalid-excerpt tests now assert rejection at schema validation, before semantic validation. No automatic retry policy or owner approval boundary changed.

Valid citations establish provenance, not whether the prose follows from the evidence. Reports still require substantive review, explicit unresolved evidence, and owner acceptance. The original rejected job remains untouched.
