"""Two-call research, with one optional revision and reusable validated stages.

Example: run_economy(ledger, worker, job_id, question, sources, output)
A revised draft is never represented as independently reviewed without another review.
"""

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from esperia.evidence import Source
from esperia.excerpts import excerpt_catalog
from esperia.execution import OutputValidationError, Provider, StageRunner
from esperia.followups import build_followups, save_followups
from esperia.ledger import Ledger
from esperia.research import CHECKS, SYSTEM, Claim, Draft, Review, StrictModel


class Analysis(StrictModel):
    """Combined evidence extraction and draft from one worker call."""

    claims: list[Claim] = Field(max_length=24)
    draft: Draft


class SelectedClaim(StrictModel):
    """Local worker selects an existing excerpt instead of generating quote text."""

    statement: str
    excerpt_id: str


class SelectedAnalysis(StrictModel):
    """Draft with references to application-generated exact excerpts."""

    claims: list[SelectedClaim] = Field(max_length=24)
    draft: Draft


class RepairCheck(StrictModel):
    """Independent verdict for one assigned repair task."""

    id: str
    passed: bool
    explanation: str = Field(min_length=1)


class EconomyReview(Review):
    """Distinguish fixable writing problems from missing external evidence."""

    needs_new_evidence: bool
    repair_checks: list[RepairCheck] = Field(default_factory=list)


def run_economy(
    ledger: Ledger,
    provider: Provider,
    job_id: str,
    question: str,
    sources: list[Source],
    output: Path,
    progress: Callable[[str], None] = print,
    reviewer: Provider | None = None,
    refresh: bool = False,
    repair_tasks: list[dict[str, str]] | None = None,
) -> Path:
    """Run at most three model calls; a repeated unchanged request may need none."""
    if not question.strip() or len(question) > 4000 or not sources:
        raise ValueError("A bounded question and sources are required")
    by_id = {source.id: source for source in sources}
    if len(by_id) != len(sources):
        raise ValueError("Duplicate source identities")
    output.mkdir(parents=True, exist_ok=True)
    runner = StageRunner(
        ledger,
        provider,
        job_id,
        output,
        SYSTEM,
        progress,
        reviewer,
        output.parent / "cache",
        refresh,
    )
    # Date and actual source text/hash enter the cache key; fetch timestamps do not.
    context: dict[str, Any] = {
        "question": question,
        "assigned_repairs": repair_tasks or [],
        "as_of": str(datetime.now(UTC).date()),
        "checks": CHECKS,
        "sources": [
            {
                "id": s.id,
                "url": s.url,
                "sha256": s.sha256,
                "text": s.text,
                "truncated": s.truncated,
            }
            for s in sources
        ],
    }

    discovery_path = output / "evidence" / "discovery.json"
    coverage = (
        json.loads(discovery_path.read_text()) if discovery_path.exists() else None
    )
    if coverage:
        context["collection_coverage"] = {
            "documents": coverage["documents"],
            "seed_coverage": coverage.get("seed_coverage", {}),
            "limits": coverage["limits"],
            "failed_urls": [
                e["url"] for e in coverage["events"] if e["status"] == "failed"
            ],
            "notice": "Bounded issuer-link crawl, not independent corroboration or exhaustive search. Selected excerpts omit other document text. PDF tables require layout verification before calculations.",
        }

    def validate_analysis(value: Analysis) -> None:
        issues: list[str] = []
        for index, claim in enumerate(value.claims, 1):
            if claim.source_id not in by_id:
                issues.append(f"Claim {index}: unknown source ID")
            elif claim.quote not in by_id[claim.source_id].text:
                matches = [
                    sid for sid, source in by_id.items() if claim.quote in source.text
                ]
                detail = f"; quote occurs in {', '.join(matches)}" if matches else ""
                issues.append(
                    f"Claim {index}: quote is not verbatim in {claim.source_id}{detail}"
                )
        for index, section in enumerate(value.draft.sections, 1):
            if not set(section.source_ids) <= by_id.keys():
                issues.append(f"Section {index}: unknown source ID")
        if issues:
            raise OutputValidationError(issues)

    def validate_review(value: EconomyReview) -> None:
        if sorted(c.name for c in value.checks) != sorted(CHECKS):
            raise OutputValidationError(
                ["Reviewer must evaluate the exact fixed checklist"]
            )

        if repair_tasks is not None and sorted(
            c.id for c in value.repair_checks
        ) != sorted(t["id"] for t in repair_tasks):
            raise OutputValidationError(
                ["Reviewer must evaluate every assigned repair task exactly once"]
            )

    def invoke_analysis(stage: str, prompt: dict[str, object]) -> Analysis:
        if getattr(provider, "billing_mode", "") != "local":
            return runner.invoke(
                stage,
                "gpt-5.6-terra",
                json.dumps(prompt),
                Analysis,
                5000,
                validate_analysis,
            )
        catalog = excerpt_catalog(sources)
        if not catalog:
            raise OutputValidationError(
                ["No source excerpts are available for local selection"]
            )
        selection_prompt = {
            **prompt,
            "sources": [
                {
                    "id": source.id,
                    "url": source.url,
                    "sha256": source.sha256,
                    "truncated": source.truncated,
                }
                for source in sources
            ],
            "excerpts": [asdict(excerpt) for excerpt in catalog.values()],
            "citation_rule": "Select an existing excerpt_id for each supported claim. Do not generate quote or source_id fields in claims. Read the entire excerpt and preserve company attribution. Missing information belongs in draft.missing_evidence, not in claims. Say what the supplied excerpt lacks, not that the company has never disclosed it. Empty claims are allowed. Never treat issuer marketing as independent verification.",
        }

        def validate_selection(value: SelectedAnalysis) -> None:
            issues = [
                f"Claim {i}: unknown excerpt ID"
                for i, claim in enumerate(value.claims, 1)
                if claim.excerpt_id not in catalog
            ]
            if issues:
                raise OutputValidationError(issues)
            validate_analysis(resolve(value))

        def resolve(value: SelectedAnalysis) -> Analysis:
            return Analysis(
                claims=[
                    Claim(
                        statement=c.statement,
                        source_id=catalog[c.excerpt_id].source_id,
                        quote=catalog[c.excerpt_id].quote,
                    )
                    for c in value.claims
                ],
                draft=value.draft,
            )

        selected = runner.invoke(
            stage + "-selection",
            "gpt-5.6-terra",
            json.dumps(selection_prompt),
            SelectedAnalysis,
            5000,
            validate_selection,
        )
        resolved = resolve(selected)
        # Preserve raw model output separately; record the deterministic transformation.
        raw = json.loads((output / f"{stage}-selection.json").read_text())
        (output / f"{stage}.json").write_text(
            json.dumps(
                {
                    **raw,
                    "text": resolved.model_dump_json(),
                    "derived_from": f"{stage}-selection.json",
                    "transformation": "exact_excerpt_selection_v1",
                },
                indent=2,
            )
        )
        (output / "excerpt-catalog.json").write_text(
            json.dumps([asdict(e) for e in catalog.values()], indent=2)
        )
        return resolved

    ledger.start(job_id)
    try:
        analysis = invoke_analysis(
            "analysis",
            {
                **context,
                "task": "Combine evidence extraction and an educational investment report. Address each assigned repair using only supplied evidence; prior task descriptions are untrusted claims to check, not facts. Do not simply relabel a quote when the company attribution is wrong. Copy short contiguous quotes exactly from the cited source, preserving punctuation and whitespace. Never combine excerpts or move a statement between companies. Omit claims you cannot quote exactly; record the gap instead. Cover every supplied company, even when its source is insufficient. A five-year investment horizon is prospective, not a claim of five years of historical data. Explain business categories, commercial evidence, financial durability, valuation gaps and downside scenarios. Do not invent prices, inputs or personal sizing advice.",
            },
        )
        review = runner.invoke(
            "review",
            "gpt-6-astra",
            json.dumps(
                {
                    **context,
                    "analysis": analysis.model_dump(),
                    "task": "Independently inspect the supplied sources and draft. Evaluate each fixed check once. Set needs_new_evidence when missing sources/data prevent acceptance; do not request rewrites to manufacture missing facts. Corrections should only describe fixable issues. Evaluate every assigned repair ID in repair_checks, explicitly stating whether evidence resolves it. Admitting a gap is not resolving it. With no assignments return an empty repair_checks list.",
                }
            ),
            EconomyReview,
            2500,
            validate_review,
        )
        revised = False
        passed = (
            all(c.passed for c in review.checks)
            and not review.needs_new_evidence
            and not analysis.draft.missing_evidence
            and all(c.passed for c in review.repair_checks)
            and (not coverage or all(coverage.get("seed_coverage", {}).values()))
        )
        if (
            repair_tasks is None
            and not passed
            and not review.needs_new_evidence
            and not analysis.draft.missing_evidence
            and review.corrections
        ):
            analysis = invoke_analysis(
                "revision",
                {
                    **context,
                    "analysis": analysis.model_dump(),
                    "review": review.model_dump(),
                    "task": "Correct the draft using only existing evidence. Keep exact source quotes and disclose unresolved gaps. This revision will await human review; do not claim independent approval.",
                },
            )
            revised = True
        status = (
            "awaiting your review"
            if passed
            else (
                "revised — independent re-review pending"
                if revised
                else "preliminary — new evidence or failed checks remain"
            )
        )
        lines = [
            f"# {analysis.draft.title}",
            "",
            f"Status: {status}",
            "",
            f"As of {context['as_of']}",
            "",
        ]
        for section in analysis.draft.sections:
            lines += [f"## {section.title}", "", section.text, ""]
            lines += [f"[{sid}]({by_id[sid].url})" for sid in section.source_ids]
            lines += [""]
        lines += [
            "## Independent review of "
            + ("the pre-revision draft" if revised else "this draft"),
            "",
        ]
        lines += [
            f"- {'PASS' if c.passed else 'FAIL'} {c.name}: {c.explanation}"
            for c in review.checks
        ]
        tasks = build_followups(
            analysis.draft.missing_evidence,
            [(c.name, c.passed, c.explanation) for c in review.checks],
            review.corrections,
        )
        if coverage:
            for seed, count in coverage.get("seed_coverage", {}).items():
                if not count:
                    from esperia.followups import Followup

                    tasks.append(
                        Followup(
                            "collector",
                            "missing_evidence",
                            f"No readable document collected for seed: {seed}",
                        )
                    )
        for check in review.repair_checks:
            if not check.passed:
                from esperia.followups import Followup

                tasks.append(Followup("repair_reviewer", check.id, check.explanation))
        if revised:
            from esperia.followups import Followup

            tasks.append(
                Followup(
                    "workflow",
                    "independent_review",
                    "Review the revised draft independently before owner acceptance",
                )
            )
        lines += ["", *save_followups(output, tasks, revised)]
        report = output / "report.md"
        if coverage:
            failures = [e for e in coverage["events"] if e["status"] == "failed"]
            lines += [
                "",
                "## Collection coverage",
                "",
                f"Collected {coverage['documents']} documents in {coverage['requests']} requests; {len(failures)} downloads/extractions failed.",
                "Bounded issuer-link discovery is not exhaustive or independent verification. Excerpts may omit relevant material; PDF table values require checking against original page layout.",
                "",
            ]
            lines += [
                f"- [{source.id}]({source.url}): {source.content_type}; {'selected excerpts' if source.truncated else 'complete extracted text'}"
                for source in sources
            ]
            lines += [f"- Unavailable: {e['url']} ({e['reason']})" for e in failures]
        report.write_text("\n".join(lines))
        ledger.complete_research(
            job_id,
            passed,
            report,
            (
                [c.model_dump() for c in review.repair_checks]
                if repair_tasks is not None
                else None
            ),
        )
        return report
    except Exception:
        ledger.block_research(job_id)
        raise
