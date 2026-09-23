"""Versioned city knowledge graph with scoped views and explicit relationships.

Example: book = Notebook(Path('library.sqlite')); note = book.create(Note(...))
Collections group shared nodes; they are not independent databases or proof of truth.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator

from esperia.evidence import Source


class EvidenceReference(BaseModel):
    """Citation metadata; manually supplied references are not auto-verified."""

    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    quote: str = ""
    source_id: str | None = None
    job_id: str | None = None


class Note(BaseModel):
    """A revision's research content, attribution and visibility.

    Kind and collection names are author-defined. No discipline list is embedded.
    Author IDs are durable attribution strings, not model names or authentication.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(max_length=100000)
    kind: str = Field(min_length=1, max_length=100)
    author_id: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    scope: Literal["owner", "public"] = "owner"
    collections: list[str] = Field(default_factory=list, max_length=100)
    task_id: str | None = None
    hypothesis_id: str | None = None
    as_of: date | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=100)
    assumptions: list[str] = Field(default_factory=list, max_length=100)
    counterevidence: list[str] = Field(default_factory=list, max_length=100)
    confidence_rationale: str = Field(default="", max_length=10000)
    next_test: str = Field(default="", max_length=10000)

    @field_validator("collections")
    @classmethod
    def distinct_collections(cls, values: list[str]) -> list[str]:
        """Canonicalize labels without collapsing case-distinct disciplines."""
        labels = [value.strip() for value in values]
        if any(not value or len(value) > 200 for value in labels):
            raise ValueError("Collection labels must contain 1–200 characters")
        return sorted(set(labels))


class Link(BaseModel):
    """A relationship pinned to the exact revisions its author compared."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    scope: Literal["owner", "public"] = "owner"
    source_id: str
    source_revision: int = Field(ge=1)
    target_id: str
    target_revision: int = Field(ge=1)
    relation: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=10000)
    author_id: str = Field(min_length=1, max_length=200)


class NotebookError(ValueError):
    """Application-authored notebook diagnostics safe for the owner console."""


class NotebookConflict(NotebookError):
    """The caller edited an outdated revision or attempted conflicting import."""


class Notebook:
    """Local owner repository; public projections omit restricted nodes and edges.

    The eventual API must authenticate callers before allowing owner access.
    SQLite transactions provide atomic revisions and optimistic concurrency.
    """

    def __init__(self, path: Path, timeout: float = 5):
        self.path, self.timeout = path, timeout
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS notebook_nodes (
                    id TEXT PRIMARY KEY, head INTEGER NOT NULL, scope TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notebook_revisions (
                    node_id TEXT NOT NULL REFERENCES notebook_nodes(id),
                    revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(node_id, revision)
                );
                CREATE TABLE IF NOT EXISTS notebook_links (
                    id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                    source_revision INTEGER NOT NULL, target_id TEXT NOT NULL,
                    target_revision INTEGER NOT NULL, relation TEXT NOT NULL,
                    rationale TEXT NOT NULL, author_id TEXT NOT NULL, created_at TEXT NOT NULL, scope TEXT NOT NULL,
                    FOREIGN KEY(source_id,source_revision) REFERENCES notebook_revisions(node_id,revision),
                    FOREIGN KEY(target_id,target_revision) REFERENCES notebook_revisions(node_id,revision),
                    UNIQUE(source_id,source_revision,target_id,target_revision,relation,author_id)
                );
                CREATE INDEX IF NOT EXISTS notebook_links_target ON notebook_links(target_id);
            """)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Close every connection, committing only successful transactions."""
        db = sqlite3.connect(self.path, timeout=self.timeout)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def record(row: sqlite3.Row) -> dict[str, Any]:
        """Return portable graph data, keeping identity outside revision content."""
        return {
            "id": row["node_id"],
            "revision": row["revision"],
            "created_at": row["created_at"],
            "note": json.loads(row["payload"]),
        }

    def create(self, note: Note) -> dict[str, Any]:
        """Persist an initial revision under a stable, model-independent UUID."""
        identity = str(uuid4())
        with self.connection() as db:
            self._create(db, identity, note)
        return self.get(identity)

    @staticmethod
    def _create(db: sqlite3.Connection, identity: str, note: Note) -> None:
        db.execute(
            "INSERT INTO notebook_nodes VALUES (?,?,?)", (identity, 1, note.scope)
        )
        db.execute(
            "INSERT INTO notebook_revisions VALUES (?,?,?,?)",
            (identity, 1, datetime.now(UTC).isoformat(), note.model_dump_json()),
        )

    def get(
        self, identity: str, revision: int | None = None, *, public: bool = False
    ) -> dict[str, Any]:
        """Get current or historical content; restricted and absent nodes look alike."""
        with self.connection() as db:
            row = db.execute(
                "SELECT r.* FROM notebook_revisions r JOIN notebook_nodes n ON n.id=r.node_id WHERE n.id=? AND r.revision=COALESCE(?,n.head) AND (?=0 OR n.scope='public')",
                (identity, revision, int(public)),
            ).fetchone()
        if row is None:
            raise NotebookError("Notebook entry not found")
        return self.record(row)

    def revise(
        self, identity: str, expected_revision: int, note: Note
    ) -> dict[str, Any]:
        """Append history atomically; never silently overwrite another author's work.

        Scope changes require a future explicit publication workflow. Editing an
        owner note cannot implicitly publish its history or existing relationships.
        """
        with self.connection() as db:
            changed = db.execute(
                "UPDATE notebook_nodes SET head=head+1 WHERE id=? AND head=? AND scope=?",
                (identity, expected_revision, note.scope),
            ).rowcount
            if changed != 1:
                raise NotebookConflict(
                    "Missing entry, stale revision or attempted visibility change"
                )
            db.execute(
                "INSERT INTO notebook_revisions VALUES (?,?,?,?)",
                (
                    identity,
                    expected_revision + 1,
                    datetime.now(UTC).isoformat(),
                    note.model_dump_json(),
                ),
            )
        return self.get(identity, expected_revision + 1)

    def connect(self, link: Link) -> dict[str, Any]:
        """Store explicit support, contradiction or other author-defined relation."""
        identity = str(uuid4())
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for node, revision in (
                (link.source_id, link.source_revision),
                (link.target_id, link.target_revision),
            ):
                row = db.execute(
                    "SELECT head FROM notebook_nodes WHERE id=?", (node,)
                ).fetchone()
                if row is None or row["head"] != revision:
                    raise NotebookConflict("Link endpoints must name current revisions")
            existing = db.execute(
                "SELECT * FROM notebook_links WHERE source_id=? AND source_revision=? AND target_id=? AND target_revision=? AND relation=? AND author_id=?",
                (
                    link.source_id,
                    link.source_revision,
                    link.target_id,
                    link.target_revision,
                    link.relation,
                    link.author_id,
                ),
            ).fetchone()
            if existing:
                if (
                    existing["rationale"] != link.rationale
                    or existing["scope"] != link.scope
                ):
                    raise NotebookConflict(
                        "Relationship already exists with a different rationale"
                    )
                return dict(existing)
            db.execute(
                "INSERT INTO notebook_links VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    link.source_id,
                    link.source_revision,
                    link.target_id,
                    link.target_revision,
                    link.relation,
                    link.rationale,
                    link.author_id,
                    datetime.now(UTC).isoformat(),
                    link.scope,
                ),
            )
            row = db.execute(
                "SELECT * FROM notebook_links WHERE id=?", (identity,)
            ).fetchone()
            assert row is not None
            return dict(row)

    def graph(
        self,
        *,
        collection: str | None = None,
        query: str = "",
        public: bool = False,
        after: str = "",
        limit: int = 100,
        edge_limit: int = 1000,
    ) -> dict[str, Any]:
        """Return a bounded graph page with internal edges and incoming backlinks.

        Collection views share global node identities. Edges remain pinned to
        revisions and are flagged stale after edits. Only edges within this page
        are returned; a paged graph must never pretend to be a complete city view.
        """
        if not 1 <= limit <= 1000 or not 1 <= edge_limit <= 10000:
            raise NotebookError("Graph node or edge limit is outside its allowed range")
        with self.connection() as db:
            db.execute("BEGIN")
            rows = db.execute(
                "SELECT r.* FROM notebook_nodes n JOIN notebook_revisions r ON r.node_id=n.id AND r.revision=n.head WHERE n.id>? AND (?=0 OR n.scope='public') AND (? IS NULL OR EXISTS (SELECT 1 FROM json_each(r.payload,'$.collections') WHERE value=?)) AND (?='' OR instr(lower(json_extract(r.payload,'$.title') || ' ' || json_extract(r.payload,'$.body')),lower(?))>0) ORDER BY n.id LIMIT ?",
                (after, int(public), collection, collection, query, query, limit + 1),
            ).fetchall()
            nodes = [self.record(r) for r in rows[:limit]]
            identities = {n["id"]: n["revision"] for n in nodes}
            edges = []
            more_edges = False
            if identities:
                slots = ",".join("?" for _ in identities)
                links = db.execute(
                    f"SELECT * FROM notebook_links WHERE source_id IN ({slots}) AND target_id IN ({slots}) AND (?=0 OR scope='public') ORDER BY id LIMIT ?",
                    (*identities, *identities, int(public), edge_limit + 1),
                ).fetchall()
                more_edges = len(links) > edge_limit
                links = links[:edge_limit]
                edges = [
                    {
                        **dict(link),
                        "stale": link["source_revision"]
                        != identities[link["source_id"]]
                        or link["target_revision"] != identities[link["target_id"]],
                    }
                    for link in links
                ]
        return {
            "schema_version": 1,
            "nodes": nodes,
            "edges": edges,
            "next_after": nodes[-1]["id"] if len(rows) > limit else None,
            "edge_scope": "within_page",
            "edges_truncated": more_edges,
        }

    def connections(
        self, identity: str, *, public: bool = False, after: str = "", limit: int = 100
    ) -> dict[str, Any]:
        """Follow paginated incoming/outgoing relationships across discipline views."""
        if not 1 <= limit <= 1000:
            raise NotebookError("Link page limit must be between 1 and 1000")
        self.get(identity, public=public)
        with self.connection() as db:
            rows = db.execute(
                "SELECT l.*, s.head AS source_head,t.head AS target_head FROM notebook_links l JOIN notebook_nodes s ON s.id=l.source_id JOIN notebook_nodes t ON t.id=l.target_id WHERE (l.source_id=? OR l.target_id=?) AND l.id>? AND (?=0 OR (s.scope='public' AND t.scope='public' AND l.scope='public')) ORDER BY l.id LIMIT ?",
                (identity, identity, after, int(public), limit + 1),
            ).fetchall()
        links = [
            {
                **dict(r),
                "stale": r["source_revision"] != r["source_head"]
                or r["target_revision"] != r["target_head"],
            }
            for r in rows[:limit]
        ]
        return {
            "edges": links,
            "next_after": links[-1]["id"] if len(rows) > limit else None,
        }

    def import_sources(
        self,
        sources: list[Source],
        *,
        author_id: str,
        role: str,
        collections: list[str],
        scope: Literal["owner", "public"] = "owner",
    ) -> list[str]:
        """Import already-verified archive documents, deduplicated by URL and hash.

        Caller must use load_archive first. Reimport is idempotent; cross-listing
        appends a revision without duplicating the underlying document identity.
        """
        identities = []
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for source in sources:
                identity = str(
                    uuid5(NAMESPACE_URL, f"esperia-source:{source.url}:{source.sha256}")
                )
                note = Note(
                    title=source.url,
                    body=source.text,
                    kind="source_document",
                    author_id=author_id,
                    role=role,
                    scope=scope,
                    collections=collections,
                    as_of=datetime.fromisoformat(source.fetched_at).date(),
                    evidence=[EvidenceReference(url=source.url, sha256=source.sha256)],
                    assumptions=[
                        "As-of date is retrieval date, not publication date.",
                        *(
                            ["Archived text is a selected or truncated projection."]
                            if source.truncated
                            else []
                        ),
                    ],
                )
                old = db.execute(
                    "SELECT n.head,n.scope,r.payload FROM notebook_nodes n JOIN notebook_revisions r ON r.node_id=n.id AND r.revision=n.head WHERE n.id=?",
                    (identity,),
                ).fetchone()
                if old:
                    existing = Note.model_validate_json(old["payload"])
                    if (
                        old["scope"] != scope
                        or existing.body != note.body
                        or existing.evidence != note.evidence
                    ):
                        raise NotebookConflict(
                            "Existing document has different visibility or content; inspect it"
                        )
                    labels = sorted(set(existing.collections + note.collections))
                    if labels != existing.collections:
                        revised = Note.model_validate(
                            {
                                **existing.model_dump(),
                                "collections": labels,
                                "author_id": author_id,
                                "role": role,
                            }
                        )
                        db.execute(
                            "UPDATE notebook_nodes SET head=head+1 WHERE id=?",
                            (identity,),
                        )
                        db.execute(
                            "INSERT INTO notebook_revisions VALUES (?,?,?,?)",
                            (
                                identity,
                                old["head"] + 1,
                                datetime.now(UTC).isoformat(),
                                revised.model_dump_json(),
                            ),
                        )
                else:
                    self._create(db, identity, note)
                identities.append(identity)
        return identities
