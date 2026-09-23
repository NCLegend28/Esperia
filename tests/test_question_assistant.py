"""Question preparation is private, bounded, versioned and never research approval."""

import json

import pytest

from esperia.execution import OutputValidationError
from esperia.ledger import Ledger, PolicyError
from esperia.notebook import Note, Notebook, NotebookConflict
from esperia.provider import Completion
from esperia.question_assistant import frame_question
from esperia.settings import Settings


class Guide:
    billing_mode = "local"
    model_name = "test-model"

    def __init__(self, ready=False):
        self.calls = 0
        self.ready = ready
        self.prompts = []

    def complete(self, model, instructions, prompt, maximum):
        self.calls += 1
        self.prompts.append(json.loads(json.loads(prompt)["task"]))
        return Completion(
            json.dumps(
                {
                    "refined_question": "Which factors are associated with consumer trust in cybersecurity products?",
                    "purpose": "Design a useful research comparison",
                    "scope": "Consumer cybersecurity products; population to clarify",
                    "clarifying_questions": (
                        []
                        if self.ready
                        else ["Individual consumers or enterprise buyers?"]
                    ),
                    "assumptions": [],
                    "premises_to_verify": [
                        "Association must not be described as causation without evidence"
                    ],
                    "subquestions": ["How is trust measured?"],
                    "evidence_needed": ["Dated empirical evidence measuring trust"],
                    "verification_plan": [
                        "Check primary methods, dates, sample sizes and contradictory results"
                    ],
                    "success_criteria": [
                        "Support each material conclusion and disclose missing evidence"
                    ],
                    "ready_for_owner_review": self.ready,
                }
            ),
            1,
            1,
            str(self.calls),
            True,
        )


def setup(tmp_path):
    settings = Settings(data_root=tmp_path)
    return settings, Ledger(tmp_path / "jobs.sqlite", 0, settings=settings)


def test_brief_stays_private_and_never_accepts_research(tmp_path):
    settings, ledger = setup(tmp_path)
    worker = Guide()
    result = frame_question(
        ledger,
        settings,
        worker,
        "What determines consumer trust?",
        collections=["cybersecurity"],
    )
    assert worker.calls == 1 and not result["research_started"]
    assert ledger.review_record(result["job_id"])["job"]["state"] == "completed"
    assert ledger.review_record(result["job_id"])["report"] is None
    book = Notebook(tmp_path / "library.sqlite")
    assert book.get(result["node_id"])["note"]["kind"] == "research_brief"
    assert book.graph(public=True)["nodes"] == []
    assert (tmp_path / "questions" / result["job_id"] / "request.json").exists()


def test_continuation_preserves_identity_and_owner_answers_across_models(tmp_path):
    settings, ledger = setup(tmp_path)
    first = frame_question(ledger, settings, Guide(), "What determines consumer trust?")
    worker = Guide(ready=True)
    worker.model_name = "different-test-model"
    second = frame_question(
        ledger,
        settings,
        worker,
        "Individual consumers, United States, 2021–2026",
        note_id=first["node_id"],
    )
    assert second["node_id"] == first["node_id"] and second["revision"] == 2
    assert second["assistant_id"] == first["assistant_id"]
    assert worker.prompts[0]["original_question"] == "What determines consumer trust?"
    assert worker.prompts[0]["owner_clarifications"] == [
        "Individual consumers, United States, 2021–2026"
    ]
    book = Notebook(tmp_path / "library.sqlite")
    assert book.get(first["node_id"], 1)["revision"] == 1
    assert len(ledger.list_jobs()) == 2


def test_turn_cap_and_wrong_note_refuse_before_model_dispatch(tmp_path):
    settings, ledger = setup(tmp_path)
    settings = settings.model_copy(update={"question_turn_limit": 1})
    worker = Guide()
    result = frame_question(ledger, settings, worker, "Question?")
    with pytest.raises(PolicyError, match="limit"):
        frame_question(ledger, settings, worker, "More", note_id=result["node_id"])
    book = Notebook(tmp_path / "library.sqlite")
    ordinary = book.create(
        Note(title="Other", body="", kind="hypothesis", author_id="owner", role="owner")
    )
    with pytest.raises(PolicyError, match="brief"):
        frame_question(ledger, settings, worker, "More", note_id=ordinary["id"])
    assert worker.calls == 1 and len(ledger.list_jobs()) == 1


def test_malformed_output_keeps_diagnostics_without_note_or_retry(tmp_path):
    settings, ledger = setup(tmp_path)

    class Invalid(Guide):
        def complete(self, *args):
            self.calls += 1
            return Completion("{}", 1, 1, "bad", True)

    worker = Invalid()
    with pytest.raises(OutputValidationError):
        frame_question(ledger, settings, worker, "Question?")
    assert worker.calls == 1
    assert Notebook(tmp_path / "library.sqlite").graph()["nodes"] == []
    assert ledger.list_jobs()[0]["state"] == "blocked"
    assert list((tmp_path / "questions").glob("*/question-framing-validation.json"))


def test_concurrent_edit_does_not_overwrite_notebook(tmp_path):
    settings, ledger = setup(tmp_path)
    original = frame_question(ledger, settings, Guide(), "Question?")

    class Editing(Guide):
        def complete(self, *args):
            book = Notebook(tmp_path / "library.sqlite")
            prior = book.get(original["node_id"])
            book.revise(
                original["node_id"],
                prior["revision"],
                Note.model_validate(prior["note"]),
            )
            return super().complete(*args)

    with pytest.raises(NotebookConflict):
        frame_question(
            ledger, settings, Editing(), "Clarification", note_id=original["node_id"]
        )
    assert (
        Notebook(tmp_path / "library.sqlite").get(original["node_id"])["revision"] == 2
    )
    assert any(job["state"] == "blocked" for job in ledger.list_jobs())


def test_uncertain_or_research_call_cannot_finish_as_preparation(tmp_path):
    _, ledger = setup(tmp_path)
    for stage, settled in [("analysis", True), ("question-framing", False)]:
        job = ledger.create_subscription("Test", 1)
        ledger.start(job)
        call = ledger.reserve_subscription_call(job, stage, "test")
        if settled:
            ledger.settle_call(call, 0, "test")
        else:
            ledger.uncertain_call(call)
        with pytest.raises(PolicyError):
            ledger.complete_preparation(job)
        assert ledger.review_record(job)["job"]["state"] == "running"


def test_cli_uses_selected_backend_and_closes_provider(tmp_path, monkeypatch, capsys):
    from esperia import cli

    worker = Guide()
    closed = []
    worker.close = lambda: closed.append(True)

    def providers(backend, settings):
        assert backend == settings.backend == "ollama"
        return worker, None

    monkeypatch.setattr(cli, "research_providers", providers)
    monkeypatch.setattr(
        "sys.argv",
        [
            "esperia",
            "--workspace",
            str(tmp_path),
            "question",
            "Help frame a question",
            "--backend",
            "ollama",
        ],
    )
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "question_preparation_only"
    assert closed == [True] and worker.calls == 1


def test_ready_brief_cannot_skip_its_own_clarifications(tmp_path):
    settings, ledger = setup(tmp_path)

    class Contradictory(Guide):
        def complete(self, *args):
            result = super().complete(*args)
            body = json.loads(result.text)
            body["ready_for_owner_review"] = True
            return Completion(json.dumps(body), 1, 1, "bad", True)

    with pytest.raises(OutputValidationError, match="unanswered"):
        frame_question(ledger, settings, Contradictory(), "Question?")
    assert Notebook(tmp_path / "library.sqlite").graph()["nodes"] == []


def test_native_schema_avoids_ollama_string_grammar_but_retains_validation():
    from pydantic import ValidationError

    from esperia.question_assistant import ResearchBrief

    schema = ResearchBrief.model_json_schema()
    assert "maxLength" not in schema["properties"]["refined_question"]
    assert "minLength" not in schema["properties"]["refined_question"]
    response = Guide().complete("test", "", json.dumps({"task": "{}"}), 100)
    body = json.loads(response.text)
    for invalid in ("", "x" * 4001):
        with pytest.raises(ValidationError):
            ResearchBrief.model_validate({**body, "refined_question": invalid})
