"""Bounded PDF extraction subprocess. Usage: python -m esperia.pdftext FILE.

Public PDFs are parsed without executing embedded actions; scanned pages need OCR.
"""

import json
import sys
from pathlib import Path

from pypdf import PdfReader

from esperia.settings import Settings


class ExtractionLimit(ValueError):
    """Application-authored, safe PDF extraction limit description."""


def extract_pdf(path: Path, settings: Settings | None = None) -> str:
    """Extract within configured page/text limits, retaining page markers."""
    settings = settings or Settings()
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ExtractionLimit("Encrypted PDF is unsupported")
    if len(reader.pages) > settings.pdf_pages:
        raise ExtractionLimit(f"PDF exceeds {settings.pdf_pages}-page extraction limit")
    parts: list[str] = []
    total = 0
    for number, page in enumerate(reader.pages, 1):
        contents = page.get_contents()
        if (
            contents is not None
            and len(contents.get_data()) > settings.pdf_stream_bytes
        ):
            raise ExtractionLimit("PDF page stream exceeds extraction bound")
        text = page.extract_text(extraction_mode="layout") or ""
        total += len(text)
        if total > settings.extracted_chars:
            raise ExtractionLimit("PDF text exceeds extraction bound")
        parts.append(f"[PDF page {number}]\n{text}")
    if sum(len(p.split("]", 1)[-1].strip()) for p in parts) < settings.minimum_text:
        raise ExtractionLimit("PDF has insufficient text; OCR may be required")
    return "\n".join(parts)


if __name__ == "__main__":
    try:
        print(
            json.dumps(
                {
                    "text": extract_pdf(
                        Path(sys.argv[1]),
                        Settings.model_validate_json(sys.stdin.read()),
                    )
                }
            )
        )
    except ExtractionLimit as error:
        print(json.dumps({"error": str(error)}))
        sys.exit(1)
    except Exception:
        print(
            json.dumps(
                {
                    "error": "PDF extraction failed or exceeded limits; OCR/encryption/layout may require manual review"
                }
            )
        )
        sys.exit(1)
