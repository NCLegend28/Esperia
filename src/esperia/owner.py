"""Read a job's report and blockers for the trusted local owner console.

Example: inspect_job(ledger, Path(".local/dev/research"), job_id)
Inspection makes no model calls and never accepts or edits a report.
"""

import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

from esperia.followups import build_followups
from esperia.ledger import Ledger, PolicyError


def inspect_job(ledger: Ledger, research_root: Path, job_id: str) -> dict[str, Any]:
    """Combine ledger state with current or legacy diagnostic artifacts."""
    try:
        if str(UUID(job_id)) != job_id:
            raise ValueError
    except ValueError:
        raise PolicyError("Use the actual job ID from esperia jobs") from None
    result = ledger.review_record(job_id)
    folder = (research_root / job_id).resolve()
    if not folder.is_relative_to(research_root.resolve()):
        raise PolicyError("Job artifact directory is outside the research root")
    result["repair"] = ledger.repair_record(job_id)
    result["calls"] = ledger.list_calls(job_id)
    result["blockers"] = []
    result["can_accept"] = False
    registered = result["report"]
    if registered:
        report = Path(registered["path"])
        intact = (
            report.is_file()
            and sha256(report.read_bytes()).hexdigest() == registered["sha256"]
        )
        result["report_intact"] = intact
        result["can_accept"] = (
            intact
            and result["job"]["state"] == "awaiting_owner"
            and all(c["state"] == "settled" for c in result["calls"])
        )
        if not intact:
            result["blockers"].append(
                "Report missing or changed since independent review"
            )
    else:
        result["legacy_report_path"] = (
            str(folder / "report.md") if (folder / "report.md").is_file() else None
        )
        result["blockers"].append(
            "No registered reviewed report; historical drafts remain inspectable but cannot be accepted through this command"
        )
    validation_tasks: list[dict[str, str]] = []
    for path in sorted(folder.glob("*-validation.json")):
        issues = json.loads(path.read_text()).get("issues", [])
        result["blockers"].extend(issues)
        validation_tasks.extend(
            {"origin": "validator", "criterion": "correction", "detail": issue}
            for issue in issues
        )
    for path in sorted(folder.glob("*-error.json")):
        error = json.loads(path.read_text())
        result["blockers"].append(
            error.get("message", "Provider failure; inspect saved stage diagnostics")
        )
    followups = folder / "followups.json"
    if followups.exists():
        result["followups"] = json.loads(followups.read_text())
    else:
        # Older jobs predate consolidated followups; derive them without modifying history.
        def body(path: Path) -> dict[str, Any]:
            try:
                value: dict[str, Any] = json.loads(json.loads(path.read_text())["text"])
                if not isinstance(value, dict):
                    raise ValueError
                return value
            except (ValueError, KeyError, TypeError):
                result["blockers"].append(
                    f"Saved output could not be parsed: {path.name}"
                )
                return {}

        candidates = [
            folder / name
            for name in [
                "revision-2.json",
                "revision-1.json",
                "revision.json",
                "draft.json",
                "analysis.json",
            ]
        ]
        draft = next((body(path) for path in candidates if path.is_file()), {})
        draft = draft.get("draft", draft)
        candidates = [
            folder / name
            for name in [
                "review-2.json",
                "review-1.json",
                "review-0.json",
                "review.json",
            ]
        ]
        review = next((body(path) for path in candidates if path.is_file()), {})
        tasks = build_followups(
            draft.get("missing_evidence", []),
            [
                (c["name"], c["passed"], c["explanation"])
                for c in review.get("checks", [])
            ],
            review.get("corrections", []),
        )
        result["followups"] = {
            "origin": "derived_from_saved_outputs",
            "tasks": [asdict(t) for t in tasks],
        }
    result["followups"]["tasks"].extend(validation_tasks)
    if result["job"]["state"] == "blocked":
        result["blockers"].append(
            "Research checks are unresolved; owner acceptance is disabled"
        )
    return result
