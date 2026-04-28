"""Two-pass curriculum-expectation extractor CLI (CB-CMCP-001 0B-2).

AI-side check only per locked decision D5=B. The OCT-certified human-side
review happens separately in stripe 0C-1; both are required for the ≥99%
Ministry-code accuracy gate. This tool is the AI half.

Usage (from repo root):

    python cli/extract_ceg.py \\
        --pdf path/to/ministry.pdf \\
        --grade 5 \\
        --subject MATH \\
        --out data/ceg-extraction/5-MATH-2020.pending.json

Output JSON shape:
    {
        "pass1_output": [<expectations>],
        "pass2_output": [<expectations>],
        "diffs":        [<items differing between passes>],
        "consensus":    [<items both passes agree on>],
        "metadata": {
            "extraction_date": "<ISO timestamp>",
            "model":           "<claude model id>",
            "source_pdf_sha256": "<hex digest>",
            "source_pdf_path":  "<original path>",
            "source_pdf_pages": <int>,
            "ministry_version": "<string|None>",
            "grade":            <int>,
            "subject":          "<string>"
        }
    }
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the repo root is on sys.path so we can import `app.*` when this
# file is invoked directly as `python cli/extract_ceg.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("cli.extract_ceg")


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PASS1_SYSTEM_PROMPT = (
    "You are an Ontario Ministry of Education curriculum analyst. "
    "Extract overall (OE) and specific (SE) expectations from the provided "
    "Ministry document text. Be precise about Ministry codes (e.g. B2.3). "
    "Paraphrase descriptions in your own words — do NOT copy Ministry prose. "
    "Return ONLY valid JSON. No prose, no markdown, no code fences."
)

PASS1_USER_PROMPT_TEMPLATE = """You are extracting Ontario curriculum expectations from this Ministry document.

Grade: {grade}
Subject: {subject}

For each Overall Expectation (OE) and Specific Expectation (SE) you find:
1. Extract the Ministry code (e.g. B2.3) if present
2. Identify if it is an OE (overall) or SE (specific)
3. Identify the Strand and Topic
4. Write a concise paraphrase in your own words (NOT copying Ministry prose)
5. Link each SE to its parent OE code

Return ONLY a valid JSON array of objects with this exact shape:
[
  {{
    "code": "B2.3",
    "type": "specific",
    "strand": "B: Number Sense",
    "topic": "Operations",
    "description": "Paraphrased description of the expectation.",
    "parent_oe_code": "B2"
  }}
]

For overall expectations, set "type" to "overall" and leave "parent_oe_code" as null.
Use null (not the string "null") for missing fields.
No prose, no markdown, no code fences. JSON only.

DOCUMENT TEXT:
---
{document_text}
---
"""


PASS2_SYSTEM_PROMPT = (
    "You are an Ontario curriculum auditor. You are checking the source "
    "Ministry document for completeness, accuracy, and code consistency. "
    "Independent extraction — do NOT rely on a prior pass. "
    "Return ONLY valid JSON. No prose, no markdown, no code fences."
)

PASS2_USER_PROMPT_TEMPLATE = """Audit the Ministry document below for ALL expectations (overall and specific) at the grade and subject level given.

Grade: {grade}
Subject: {subject}

Approach this as a fresh, independent pass — not a review of any previous output. For each expectation found in the document:
- Record the Ministry code exactly as it appears
- Mark it "overall" or "specific"
- Record the Strand and Topic from the document headings
- Provide a brief paraphrase (do NOT copy Ministry text verbatim)
- For each specific expectation, identify the parent overall expectation code

Be thorough. Do not skip codes that appear in the document.

Return ONLY a valid JSON array of objects with this exact shape:
[
  {{
    "code": "B2.3",
    "type": "specific",
    "strand": "B: Number Sense",
    "topic": "Operations",
    "description": "Paraphrased description.",
    "parent_oe_code": "B2"
  }}
]

Use null for missing fields. No prose, no markdown, no code fences. JSON only.

DOCUMENT TEXT:
---
{document_text}
---
"""


# Maximum characters of PDF text to include in a single Claude prompt.
# Keeps individual passes within reasonable token budgets; for full Ministry
# PDFs the 0B-5 stripe will chunk by section. The synthetic test fixture
# fits comfortably within this limit.
MAX_PROMPT_CHARS = 60_000

# Tokens per pass — generous enough for ~200 expectations of paraphrased JSON.
EXTRACTION_MAX_TOKENS = 4000


# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------


class PDFExtractionError(RuntimeError):
    """Raised when the input PDF cannot be parsed."""


@dataclass
class ParsedPDF:
    text: str
    page_count: int
    sha256: str
    path: str


def parse_pdf(pdf_path: Path) -> ParsedPDF:
    """Extract plain text + SHA-256 from a PDF file.

    Uses PyPDF2 (already in requirements.txt) — keeps the dependency
    footprint identical to phase-2.

    Raises PDFExtractionError on any parse failure with a helpful message.
    """
    if not pdf_path.exists():
        raise PDFExtractionError(f"PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        raise PDFExtractionError(f"Not a file: {pdf_path}")

    raw_bytes = pdf_path.read_bytes()
    if not raw_bytes:
        raise PDFExtractionError(f"PDF is empty: {pdf_path}")

    sha = hashlib.sha256(raw_bytes).hexdigest()

    try:
        from PyPDF2 import PdfReader
        from PyPDF2.errors import PdfReadError
    except ImportError as e:  # pragma: no cover - environment guard
        raise PDFExtractionError(
            "PyPDF2 is required for CLI PDF parsing. Install via "
            "`pip install -r requirements.txt`."
        ) from e

    try:
        reader = PdfReader(str(pdf_path))
    except PdfReadError as e:
        raise PDFExtractionError(f"Malformed PDF (could not read): {pdf_path} — {e}") from e
    except Exception as e:
        raise PDFExtractionError(f"Failed to open PDF: {pdf_path} — {e}") from e

    pages: list[str] = []
    for idx, page in enumerate(reader.pages):
        try:
            pages.append(page.extract_text() or "")
        except Exception as e:
            raise PDFExtractionError(
                f"Failed to extract text from page {idx + 1} of {pdf_path}: {e}"
            ) from e

    text = "\n".join(pages).strip()
    if not text:
        raise PDFExtractionError(
            f"PDF contained no extractable text (likely image-only / scanned): {pdf_path}"
        )

    return ParsedPDF(text=text, page_count=len(reader.pages), sha256=sha, path=str(pdf_path))


# ---------------------------------------------------------------------------
# Claude pass execution
# ---------------------------------------------------------------------------


def _truncate_for_prompt(document_text: str, limit: int = MAX_PROMPT_CHARS) -> str:
    if len(document_text) <= limit:
        return document_text
    logger.warning(
        "PDF text truncated from %d to %d chars for single-pass prompt; "
        "full-document chunking is deferred to stripe 0B-5.",
        len(document_text),
        limit,
    )
    return document_text[:limit]


def _strip_code_fence(raw: str) -> str:
    """Remove leading/trailing markdown code fences if Claude returned them
    despite being told not to. Keeps parsing tolerant."""
    s = raw.strip()
    fence = re.match(r"^```(?:json)?\s*\n(.*)\n```\s*$", s, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return s


def parse_pass_output(raw: str) -> list[dict[str, Any]]:
    """Parse a Claude pass response as a list of expectation dicts.

    Tolerates surrounding code fences. Raises ValueError on unparseable
    output (so the CLI can fail loudly rather than silently producing
    empty diffs).
    """
    cleaned = _strip_code_fence(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Pass output is not valid JSON: {e}") from e

    if not isinstance(data, list):
        raise ValueError(
            f"Pass output must be a JSON array; got {type(data).__name__}"
        )

    cleaned_items: list[dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(
                f"Pass output[{i}] must be an object; got {type(item).__name__}"
            )
        cleaned_items.append(item)
    return cleaned_items


async def run_pass(
    document_text: str,
    grade: int,
    subject: str,
    user_prompt_template: str,
    system_prompt: str,
) -> tuple[list[dict[str, Any]], str]:
    """Run a single Claude extraction pass.

    Returns (parsed_items, raw_response).
    """
    # Lazy import so unit tests can mock at the module path without paying
    # the import-cost of FastAPI/SQLAlchemy at CLI import time, and so the
    # mock applies cleanly.
    from app.services.ai_service import generate_content

    prompt_text = _truncate_for_prompt(document_text)
    user_prompt = user_prompt_template.format(
        grade=grade,
        subject=subject,
        document_text=prompt_text,
    )

    raw, _stop_reason = await generate_content(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=EXTRACTION_MAX_TOKENS,
        # Low temperature for reproducible structured output.
        temperature=0.1,
    )
    parsed = parse_pass_output(raw)
    return parsed, raw


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------


_DIFFABLE_FIELDS: tuple[str, ...] = (
    "type",
    "strand",
    "topic",
    "parent_oe_code",
)


def _normalize_code(code: Any) -> str:
    if code is None:
        return ""
    return str(code).strip().upper()


def _index_by_code(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        code = _normalize_code(item.get("code"))
        if not code:
            # Items without a code can't be matched across passes; skip.
            continue
        # If duplicates within a pass, keep the first occurrence.
        out.setdefault(code, item)
    return out


def diff_passes(
    pass1: list[dict[str, Any]],
    pass2: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compare two passes by Ministry code and return (diffs, consensus).

    A code present in only one pass is a `missing_in_<pass>` diff.
    A code present in both with mismatched type/strand/topic/parent is a
    `field_mismatch` diff (description differences are *not* flagged because
    each pass paraphrases independently — that's expected).
    A code present in both with matching diffable fields lands in `consensus`.
    """
    idx1 = _index_by_code(pass1)
    idx2 = _index_by_code(pass2)

    diffs: list[dict[str, Any]] = []
    consensus: list[dict[str, Any]] = []

    all_codes = sorted(set(idx1) | set(idx2))
    for code in all_codes:
        in1 = code in idx1
        in2 = code in idx2

        if in1 and not in2:
            diffs.append({
                "code": code,
                "kind": "missing_in_pass2",
                "pass1": idx1[code],
                "pass2": None,
            })
            continue
        if in2 and not in1:
            diffs.append({
                "code": code,
                "kind": "missing_in_pass1",
                "pass1": None,
                "pass2": idx2[code],
            })
            continue

        item1 = idx1[code]
        item2 = idx2[code]
        mismatched_fields: list[str] = []
        for field in _DIFFABLE_FIELDS:
            v1 = item1.get(field)
            v2 = item2.get(field)
            if (v1 or None) != (v2 or None):
                mismatched_fields.append(field)

        if mismatched_fields:
            diffs.append({
                "code": code,
                "kind": "field_mismatch",
                "fields": mismatched_fields,
                "pass1": item1,
                "pass2": item2,
            })
        else:
            consensus.append({
                "code": code,
                "pass1": item1,
                "pass2": item2,
            })

    return diffs, consensus


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _claude_model_name() -> str:
    """Best-effort lookup of the configured Claude model id.

    Returns 'unknown' if app config can't be loaded (CLI must not crash on
    metadata lookup).
    """
    try:
        from app.core.config import settings
        return getattr(settings, "claude_model", "unknown") or "unknown"
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("Could not read claude model from settings: %s", e)
        return "unknown"


async def extract_ceg(
    pdf_path: Path,
    grade: int,
    subject: str,
    ministry_version: str | None,
) -> dict[str, Any]:
    """Run the full two-pass extraction and return the result dict."""
    parsed = parse_pdf(pdf_path)

    pass1_items, _raw1 = await run_pass(
        document_text=parsed.text,
        grade=grade,
        subject=subject,
        user_prompt_template=PASS1_USER_PROMPT_TEMPLATE,
        system_prompt=PASS1_SYSTEM_PROMPT,
    )
    pass2_items, _raw2 = await run_pass(
        document_text=parsed.text,
        grade=grade,
        subject=subject,
        user_prompt_template=PASS2_USER_PROMPT_TEMPLATE,
        system_prompt=PASS2_SYSTEM_PROMPT,
    )

    diffs, consensus = diff_passes(pass1_items, pass2_items)

    return {
        "pass1_output": pass1_items,
        "pass2_output": pass2_items,
        "diffs": diffs,
        "consensus": consensus,
        "metadata": {
            "extraction_date": datetime.now(timezone.utc).isoformat(),
            "model": _claude_model_name(),
            "source_pdf_sha256": parsed.sha256,
            "source_pdf_path": parsed.path,
            "source_pdf_pages": parsed.page_count,
            "ministry_version": ministry_version,
            "grade": grade,
            "subject": subject,
        },
    }


def write_output(result: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract_ceg",
        description=(
            "Two-pass Ontario curriculum expectation extractor (AI-side "
            "check only per CB-CMCP-001 D5=B). The OCT-reviewer human-side "
            "check is a separate stripe."
        ),
    )
    parser.add_argument("--pdf", required=True, type=Path, help="Path to source Ministry PDF")
    parser.add_argument("--grade", required=True, type=int, help="Grade level (1-12)")
    parser.add_argument("--subject", required=True, type=str, help="Subject code (e.g. MATH, LANG)")
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output path for pending-review JSON",
    )
    parser.add_argument(
        "--ministry-version",
        required=False,
        default=None,
        help="Ministry document version label, e.g. '2020' (optional metadata)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not (1 <= args.grade <= 12):
        print(f"ERROR: --grade must be between 1 and 12, got {args.grade}", file=sys.stderr)
        return 2

    try:
        result = asyncio.run(
            extract_ceg(
                pdf_path=args.pdf,
                grade=args.grade,
                subject=args.subject,
                ministry_version=args.ministry_version,
            )
        )
    except PDFExtractionError as e:
        print(f"ERROR: PDF extraction failed: {e}", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"ERROR: Pass output unparseable: {e}", file=sys.stderr)
        return 4
    except Exception as e:  # pragma: no cover - top-level safety net
        print(f"ERROR: Unexpected failure: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    write_output(result, args.out)

    diff_count = len(result["diffs"])
    consensus_count = len(result["consensus"])
    pass1_count = len(result["pass1_output"])
    pass2_count = len(result["pass2_output"])
    print(
        f"Wrote {args.out} | pass1={pass1_count} pass2={pass2_count} "
        f"diffs={diff_count} consensus={consensus_count}"
    )
    if diff_count > 0:
        print(
            f"NOTE: {diff_count} item(s) differ between passes — prioritize "
            f"these for OCT-reviewer attention."
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
