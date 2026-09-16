"""Consolidate evidence gaps and review failures without another model call.

Example: tasks = build_followups(["Missing share count"], [], [])
These tasks describe pending work; they never launch tools or change permissions.
"""

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Followup:
    """One traceable request for evidence or correction."""

    origin: str
    criterion: str
    detail: str


def build_followups(
    missing: Sequence[str],
    checks: Sequence[tuple[str, bool, str]],
    corrections: Sequence[str],
) -> list[Followup]:
    """Preserve every failed check, with exact duplicate tasks removed."""
    tasks = [Followup("draft", "missing_evidence", item) for item in missing]
    tasks += [
        Followup("reviewer", name, detail)
        for name, passed, detail in checks
        if not passed
    ]
    tasks += [Followup("reviewer", "correction", item) for item in corrections]
    return list(dict.fromkeys(tasks))


def save_followups(
    output: Path, tasks: Sequence[Followup], revised: bool = False
) -> list[str]:
    """Save a job's pending work and return Markdown for the report."""
    lines = ["## Evidence gaps and review follow-ups", ""]
    if revised:
        lines += [
            "Reviewer findings refer to the earlier draft; resolution requires a fresh independent review.",
            "",
        ]
    lines += [
        f"- [ ] [{task.origin}: {task.criterion}] {task.detail}" for task in tasks
    ]
    if not tasks:
        lines += ["No pending items were reported. Owner review is still required."]
    (output / "followups.json").write_text(
        json.dumps(
            {
                "status": "pending" if tasks else "none_reported",
                "review_applies_to": "pre_revision" if revised else "current_draft",
                "tasks": [asdict(task) for task in tasks],
            },
            indent=2,
        )
    )
    (output / "followups.md").write_text("\n".join(lines))
    return lines
