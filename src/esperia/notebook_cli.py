"""Local owner commands for the city knowledge graph.

Example: esperia library graph --collection energy
JSON output is data for the future Library viewer, never executable HTML.
"""

import argparse
import json
from pathlib import Path

from esperia.evidence import load_archive
from esperia.notebook import Link, Note, Notebook, NotebookError
from esperia.settings import Settings


def add_library_commands(
    commands: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    """Register bounded notebook commands under one Library entry point."""
    library = commands.add_parser("library", help="Versioned city knowledge graph")
    actions = library.add_subparsers(dest="library_action", required=True)
    create = actions.add_parser("add", help="Create a note from a JSON file")
    create.add_argument("file", type=Path)
    revise = actions.add_parser("revise", help="Append a note revision")
    revise.add_argument("id")
    revise.add_argument("file", type=Path)
    revise.add_argument("--expected-revision", type=int, required=True)
    show = actions.add_parser("show", help="Read a current or historical note")
    show.add_argument("id")
    show.add_argument("--revision", type=int)
    show.add_argument("--public", action="store_true")
    link = actions.add_parser("link", help="Connect exact note revisions from JSON")
    link.add_argument("file", type=Path)
    graph = actions.add_parser(
        "graph", help="Read a paginated global or collection graph"
    )
    graph.add_argument("--collection")
    graph.add_argument("--query", default="")
    graph.add_argument("--public", action="store_true")
    graph.add_argument("--after", default="")
    graph.add_argument("--limit", type=int)
    links = actions.add_parser(
        "links", help="Read incoming and outgoing links across collections"
    )
    links.add_argument("id")
    links.add_argument("--public", action="store_true")
    links.add_argument("--after", default="")
    links.add_argument("--limit", type=int)
    ingest = actions.add_parser(
        "import-archive", help="Verify and import archived source documents"
    )
    ingest.add_argument("archive", type=Path)
    ingest.add_argument("--author", required=True)
    ingest.add_argument("--role", required=True)
    ingest.add_argument("--collection", action="append", required=True)
    ingest.add_argument("--scope", choices=["owner", "public"], default="owner")


def run_library(args: argparse.Namespace, settings: Settings, workspace: Path) -> None:
    """Dispatch owner operations; public flags only narrow read projections."""
    book = Notebook(settings.data_root / "library.sqlite", settings.sqlite_timeout)
    action = args.library_action
    if action in {"add", "revise", "link"}:
        path = workspace / args.file
        with path.open("rb") as stream:
            data = stream.read(settings.notebook_input_bytes + 1)
        if len(data) > settings.notebook_input_bytes:
            raise NotebookError("Notebook input exceeds its configured byte budget")
        if action == "link":
            result = book.connect(Link.model_validate_json(data))
        else:
            note = Note.model_validate_json(data)
            result = (
                book.create(note)
                if action == "add"
                else book.revise(args.id, args.expected_revision, note)
            )
    elif action == "show":
        result = book.get(args.id, args.revision, public=args.public)
    elif action == "graph":
        result = book.graph(
            collection=args.collection,
            query=args.query,
            public=args.public,
            after=args.after,
            limit=args.limit if args.limit is not None else settings.notebook_page_size,
            edge_limit=settings.notebook_edge_limit,
        )
    elif action == "links":
        result = book.connections(
            args.id,
            public=args.public,
            after=args.after,
            limit=args.limit if args.limit is not None else settings.notebook_page_size,
        )
    else:
        try:
            sources = load_archive(workspace / args.archive, settings)
        except (ValueError, OSError) as error:
            raise NotebookError(
                "Archive unavailable or failed integrity/freshness checks; no documents imported"
            ) from error
        ids = book.import_sources(
            sources,
            author_id=args.author,
            role=args.role,
            collections=args.collection,
            scope=args.scope,
        )
        result = {"node_ids": ids, "imported_documents": len(ids)}
    print(json.dumps(result, indent=2))
