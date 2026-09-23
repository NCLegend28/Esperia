"""Notebook revisions, cross-discipline relationships and public-view isolation."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_agent_workflow import archive

from esperia import cli
from esperia.evidence import load_archive
from esperia.notebook import Link, Note, Notebook, NotebookConflict


def note(title="Finding", **changes):
    return Note(
        title=title,
        body="A hypothesis, not an accepted result.",
        kind="hypothesis",
        author_id="researcher-1",
        role="researcher",
        **changes,
    )


def edge(a, b, **changes):
    return Link(
        source_id=a["id"],
        source_revision=a["revision"],
        target_id=b["id"],
        target_revision=b["revision"],
        relation="contradicts",
        rationale="Different evidence needs investigation",
        author_id="reviewer-1",
        **changes,
    )


def test_one_graph_multiple_collections_and_backlinks(tmp_path):
    book = Notebook(tmp_path / "library.sqlite")
    a = book.create(note("Energy", collections=["energy", "economics"]))
    b = book.create(note("Environment", collections=["ecology"]))
    connection = book.connect(edge(a, b))
    assert book.graph(collection="economics")["nodes"][0]["id"] == a["id"]
    assert len(book.graph()["nodes"]) == 2
    assert book.connections(b["id"])["edges"][0]["id"] == connection["id"]
    assert book.connections(a["id"])["edges"][0]["id"] == connection["id"]
    assert book.connect(edge(a, b))["id"] == connection["id"]
    assert len(book.graph(collection="ecology")["edges"]) == 0
    assert book.graph(query="ENERGY")["nodes"][0]["id"] == a["id"]


def test_history_and_stale_links_survive_reopen(tmp_path):
    path = tmp_path / "library.sqlite"
    book = Notebook(path)
    a, b = book.create(note()), book.create(note("Counterevidence"))
    book.connect(edge(a, b))
    revised = book.revise(
        a["id"],
        1,
        note(
            "Revised hypothesis",
            assumptions=["Uncertain"],
            next_test="Obtain dated primary evidence",
        ),
    )
    assert revised["revision"] == 2
    reopened = Notebook(path)
    assert reopened.get(a["id"], 1)["note"]["title"] == "Finding"
    assert reopened.graph()["edges"][0]["stale"]
    with pytest.raises(NotebookConflict):
        reopened.connect(edge(a, b))
    with pytest.raises(NotebookConflict):
        reopened.revise(a["id"], 1, note("Lost edit"))
    assert reopened.get(a["id"])["note"]["title"] == "Revised hypothesis"


def test_concurrent_revisions_cannot_overwrite(tmp_path):
    book = Notebook(tmp_path / "library.sqlite")
    a = book.create(note())

    def revise(title):
        try:
            book.revise(a["id"], 1, note(title))
            return True
        except NotebookConflict:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(revise, ["First", "Second"])) == [False, True]
    assert book.get(a["id"])["revision"] == 2


def test_public_views_do_not_leak_private_nodes_or_relationships(tmp_path):
    book = Notebook(tmp_path / "library.sqlite")
    a, b = book.create(note("Public A", scope="public")), book.create(
        note("Public B", scope="public")
    )
    private = book.create(note("Confidential", collections=["secret"]))
    book.connect(edge(a, b))  # Private rationale even though endpoints are public.
    book.connect(edge(a, private, scope="public"))
    assert len(book.graph(public=True)["nodes"]) == 2
    assert book.graph(public=True)["edges"] == []
    assert book.connections(a["id"], public=True)["edges"] == []
    for method in (book.get, book.connections):
        with pytest.raises(ValueError, match="not found"):
            method(private["id"], public=True)
    with pytest.raises(NotebookConflict):
        book.revise(private["id"], 1, note(scope="public"))
    assert not book.graph(collection="secret", public=True)["nodes"]


def test_pagination_and_edge_bounds_are_explicit(tmp_path):
    book = Notebook(tmp_path / "library.sqlite")
    nodes = [book.create(note(str(i))) for i in range(3)]
    book.connect(edge(nodes[0], nodes[1]))
    book.connect(edge(nodes[1], nodes[2]))
    page = book.graph(limit=2)
    final = book.graph(after=page["next_after"], limit=2)
    assert len({n["id"] for n in page["nodes"] + final["nodes"]}) == 3
    assert final["next_after"] is None
    graph = book.graph(edge_limit=1)
    assert len(graph["edges"]) == 1 and graph["edges_truncated"]
    assert book.graph(query="' OR 1=1 --")["nodes"] == []


def test_archive_import_idempotency_and_cross_listing(tmp_path):
    archive(["https://example.com/report"], "Research", tmp_path / "evidence")
    sources = load_archive(tmp_path / "evidence")
    book = Notebook(tmp_path / "library.sqlite")
    kwargs = {
        "author_id": "librarian-1",
        "role": "librarian",
        "collections": ["energy"],
    }
    first = book.import_sources(sources, **kwargs)
    assert book.import_sources(sources, **kwargs) == first
    assert book.get(first[0])["revision"] == 1
    kwargs["collections"] = ["economics"]
    assert book.import_sources(sources, **kwargs) == first
    assert book.get(first[0])["note"]["collections"] == ["economics", "energy"]
    assert len(book.graph()["nodes"]) == 1
    assert book.get(first[0], 1)["note"]["collections"] == ["energy"]
    with pytest.raises(NotebookConflict):
        book.import_sources(sources, scope="public", **kwargs)


def test_invalid_link_and_conflicting_rationale_are_rejected(tmp_path):
    book = Notebook(tmp_path / "library.sqlite")
    a, b = book.create(note()), book.create(note("B"))
    link = edge(a, b)
    book.connect(link)
    with pytest.raises(NotebookConflict):
        book.connect(link.model_copy(update={"rationale": "New unsupported relation"}))
    with pytest.raises(NotebookConflict):
        book.connect(link.model_copy(update={"target_id": "missing"}))


def test_cli_create_show_and_public_projection(tmp_path, monkeypatch, capsys):
    path = tmp_path / "note.json"
    path.write_text(note(collections=["test"]).model_dump_json())
    monkeypatch.setattr(
        "sys.argv",
        ["esperia", "--workspace", str(tmp_path), "library", "add", str(path)],
    )
    cli.main()
    result = json.loads(capsys.readouterr().out)
    monkeypatch.setattr(
        "sys.argv",
        ["esperia", "--workspace", str(tmp_path), "library", "show", result["id"]],
    )
    cli.main()
    assert json.loads(capsys.readouterr().out)["note"]["author_id"] == "researcher-1"
    monkeypatch.setattr(
        "sys.argv",
        ["esperia", "--workspace", str(tmp_path), "library", "graph", "--public"],
    )
    cli.main()
    assert json.loads(capsys.readouterr().out)["nodes"] == []


def test_public_relationship_is_visible_but_still_revision_bound(tmp_path):
    book = Notebook(tmp_path / "library.sqlite")
    a, b = book.create(note("A", scope="public")), book.create(
        note("B", scope="public")
    )
    link = book.connect(edge(a, b, scope="public"))
    assert book.graph(public=True)["edges"][0]["id"] == link["id"]
    book.revise(a["id"], 1, note("A revised", scope="public"))
    assert book.connections(b["id"], public=True)["edges"][0]["stale"]


def test_import_failure_rolls_back_whole_batch(tmp_path):
    sources = archive(["https://example.com/report"], "Research", tmp_path / "evidence")
    book = Notebook(tmp_path / "library.sqlite")
    kwargs = {"author_id": "owner", "role": "librarian", "collections": ["energy"]}
    book.import_sources(sources, **kwargs)
    new = sources[0].model_copy(update={"url": "https://example.com/new"})
    conflict = sources[0].model_copy(update={"text": "Changed projection"})
    with pytest.raises(NotebookConflict):
        book.import_sources([new, conflict], **kwargs)
    assert len(book.graph()["nodes"]) == 1


def test_cli_rejects_corrupted_archive_without_importing(tmp_path, monkeypatch, capsys):
    archive(["https://example.com/report"], "Research", tmp_path / "evidence")
    next((tmp_path / "evidence").glob("*.source")).write_text("corrupt")
    monkeypatch.setattr(
        "sys.argv",
        [
            "esperia",
            "--workspace",
            str(tmp_path),
            "library",
            "import-archive",
            str(tmp_path / "evidence"),
            "--author",
            "owner",
            "--role",
            "librarian",
            "--collection",
            "energy",
        ],
    )
    with pytest.raises(SystemExit):
        cli.main()
    assert "integrity/freshness" in capsys.readouterr().err
    assert Notebook(tmp_path / ".local/dev/library.sqlite").graph()["nodes"] == []
