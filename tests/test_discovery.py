"""Bounded traversal, actual PDF text extraction, document-wide retrieval and integrity."""

import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from esperia.discovery import BREAK, discover, projected_text, select_passages
from esperia.evidence import load_archive
from esperia.excerpts import excerpt_catalog
from esperia.settings import Profile, Settings


def test_follow_financial_link_and_record_failure(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<p>"
                + "Company investor information. " * 6
                + '</p><a href="/annual-report">Annual report 2026</a><a href="/earnings">Earnings</a><a href="https://evil.example/annual.pdf">Annual PDF</a>',
            )
        if request.url.path == "/earnings":
            return httpx.Response(403)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<p>"
            + "Annual financial report cash flow debt warrants. " * 20
            + "</p>",
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as client:
        sources = discover(
            ["https://ir.arqit.uk/"],
            "financial cash flow",
            tmp_path,
            max_documents=3,
            max_requests=4,
            client=client,
            settings=Settings(
                allowed_hosts=["ir.arqit.uk"],
                profile=Profile(discovery_terms=["annual", "earnings"]),
            ),
        )
    assert len(sources) == 2
    assert any(s.discovered_from for s in sources)
    assert all("evil.example" not in url for url in calls)
    log = json.loads((tmp_path / "discovery.json").read_text())
    assert any(e["status"] == "failed" for e in log["events"])
    assert any(e["status"] == "outside_policy" for e in log["events"])
    assert load_archive(tmp_path) == sources
    data = json.loads((tmp_path / "sources.json").read_text())
    data[0]["text"] = "Changed evidence"
    (tmp_path / "sources.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="modified"):
        load_archive(tmp_path)


def test_query_selects_late_financial_material() -> None:
    text = (
        "Company introduction. " * 900
        + " Cash flow liquidity debt warrants risk factors " * 100
    )
    ranges = select_passages(text, "liquidity", 3000)
    assert any(start > 12000 for start, _ in ranges)
    assert len(projected_text(text, ranges)) <= 3000


def pdf_bytes() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 10 Tf 30 700 Td (Annual financial report: revenue cash flow debt and liquidity. Revenue is reported for the fiscal year. Figures require independent verification.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_extraction_and_archive_roundtrip(tmp_path: Path) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, headers={"content-type": "application/pdf"}, content=pdf_bytes()
            )
        )
    ) as client:
        sources = discover(
            ["https://ir.arqit.uk/annual.pdf"],
            "cash flow",
            tmp_path,
            max_documents=1,
            max_requests=1,
            client=client,
        )
    assert sources[0].content_type == "application/pdf"
    assert "Annual financial report" in sources[0].text
    assert "[PDF page 1]" in sources[0].text
    assert load_archive(tmp_path) == sources


def test_redirect_to_private_host_never_requested(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    with httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as client:
        with pytest.raises(ValueError, match="no readable"):
            discover(
                ["https://ir.arqit.uk/"],
                "financial",
                tmp_path,
                max_documents=1,
                max_requests=2,
                client=client,
            )
    assert calls == ["https://ir.arqit.uk/"]


def test_excerpt_quotes_do_not_span_omissions() -> None:
    from esperia.evidence import Source

    source = Source(
        id="S1",
        url="https://ir.arqit.uk/",
        fetched_at="2026-09-15T00:00:00Z",
        sha256="a" * 64,
        text="First passage with source text."
        + BREAK
        + "Second separate passage with source text.",
        truncated=True,
    )
    assert all(BREAK not in e.quote for e in excerpt_catalog([source]).values())


def test_request_budget_and_missing_seed_coverage(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.host == "www.ionq.com":
            return httpx.Response(403)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="Public financial information " * 10
            + '<a href="/annual-report">Annual report</a>',
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as client:
        discover(
            ["https://ir.arqit.uk/", "https://www.ionq.com/"],
            "annual",
            tmp_path,
            max_documents=2,
            max_requests=2,
            client=client,
        )
    log = json.loads((tmp_path / "discovery.json").read_text())
    assert len(calls) == 2
    assert log["seed_coverage"]["https://www.ionq.com/"] == 0
    assert log["seed_coverage"]["https://ir.arqit.uk/"] == 1


def test_index_children_precede_unrelated_sibling_links(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        links = (
            '<a href="/annual-reports">Annual reports</a><a href="/earnings">Earnings news</a>'
            if request.url.path == "/"
            else (
                '<a href="/10-k-report">10-K annual filing</a>'
                if request.url.path == "/annual-reports"
                else ""
            )
        )
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="Financial document details " * 10 + links,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as client:
        discover(
            ["https://ir.arqit.uk/"],
            "annual",
            tmp_path,
            max_documents=3,
            max_requests=3,
            client=client,
        )
    assert calls == ["/", "/annual-reports", "/10-k-report"]


def test_filing_table_context_ranks_opaque_document_links() -> None:
    from esperia.discovery import Links, link_score

    parser = Links()
    parser.feed(
        '<table><tr><td>2026 10-Q Quarterly financial statements</td><td><a href="/static-files/abc">PDF</a></td></tr></table>'
    )
    href, label = parser.links[0]
    assert link_score(
        href,
        label,
        "cash flow",
        Settings(profile=Profile(discovery_terms=["10-q", "financial"])),
    ) > link_score("/financial-information/sec-filings", "SEC Filings", "cash flow")
    assert link_score("/privacy", "Privacy", "financial") == 0


def test_final_redirect_attempt_is_logged(tmp_path: Path) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                302, headers={"location": "https://ir.arqit.uk/annual-report"}
            )
        ),
        follow_redirects=False,
    ) as client:
        with pytest.raises(ValueError, match="no readable"):
            discover(
                ["https://ir.arqit.uk/"],
                "annual",
                tmp_path,
                max_documents=1,
                max_requests=1,
                client=client,
            )
    assert (
        json.loads((tmp_path / "discovery.json").read_text())["events"][0]["status"]
        == "redirect"
    )
