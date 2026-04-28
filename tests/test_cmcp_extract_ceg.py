"""Unit tests for cli/extract_ceg.py — the two-pass curriculum extractor.

Per CB-CMCP-001 0B-2 acceptance criteria:
- JSON output shape (pass1, pass2, diffs, consensus, metadata)
- Diff detection logic with known-divergent fake passes
- Error handling for malformed PDF
- Round-trip on synthetic fixture PDF
- Claude API is mocked — no real API calls
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure repo root is importable so `cli.extract_ceg` resolves regardless of
# how pytest is invoked.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cli import extract_ceg as ec  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cmcp"
SYNTHETIC_PDF = FIXTURES_DIR / "synthetic_curriculum_grade5_math.pdf"


# ---------------------------------------------------------------------------
# Pass-output parsing
# ---------------------------------------------------------------------------


class TestParsePassOutput:
    def test_parses_plain_json_array(self):
        raw = '[{"code": "B1", "type": "overall", "strand": "B", "topic": null, "description": "x", "parent_oe_code": null}]'
        items = ec.parse_pass_output(raw)
        assert items == [
            {
                "code": "B1",
                "type": "overall",
                "strand": "B",
                "topic": None,
                "description": "x",
                "parent_oe_code": None,
            }
        ]

    def test_strips_json_code_fence(self):
        raw = '```json\n[{"code": "B1", "type": "overall"}]\n```'
        items = ec.parse_pass_output(raw)
        assert len(items) == 1
        assert items[0]["code"] == "B1"

    def test_strips_unlabelled_code_fence(self):
        raw = '```\n[{"code": "B1"}]\n```'
        items = ec.parse_pass_output(raw)
        assert items == [{"code": "B1"}]

    def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            ec.parse_pass_output("not json at all")

    def test_top_level_object_rejected(self):
        with pytest.raises(ValueError, match="must be a JSON array"):
            ec.parse_pass_output('{"code": "B1"}')

    def test_non_object_array_element_rejected(self):
        with pytest.raises(ValueError, match=r"output\[0\] must be an object"):
            ec.parse_pass_output('["just a string"]')


# ---------------------------------------------------------------------------
# Diff logic — feed known-divergent passes and verify diffs are detected.
# ---------------------------------------------------------------------------


class TestDiffPasses:
    def test_identical_passes_all_consensus_no_diffs(self):
        items = [
            {"code": "B1", "type": "overall", "strand": "B", "topic": None,
             "description": "p1", "parent_oe_code": None},
            {"code": "B1.1", "type": "specific", "strand": "B", "topic": "Numbers",
             "description": "p1", "parent_oe_code": "B1"},
        ]
        diffs, consensus = ec.diff_passes(items, items)
        assert diffs == []
        assert len(consensus) == 2
        assert {c["code"] for c in consensus} == {"B1", "B1.1"}

    def test_different_descriptions_dont_count_as_diff(self):
        # Each pass paraphrases independently — that's expected, not a diff.
        p1 = [{"code": "B1", "type": "overall", "strand": "B", "topic": None,
               "description": "Pass 1 paraphrase", "parent_oe_code": None}]
        p2 = [{"code": "B1", "type": "overall", "strand": "B", "topic": None,
               "description": "Pass 2 phrasing differs", "parent_oe_code": None}]
        diffs, consensus = ec.diff_passes(p1, p2)
        assert diffs == []
        assert len(consensus) == 1

    def test_missing_in_pass2_is_diff(self):
        p1 = [
            {"code": "B1", "type": "overall", "strand": "B", "topic": None,
             "description": "x", "parent_oe_code": None},
            {"code": "B2", "type": "overall", "strand": "B", "topic": None,
             "description": "y", "parent_oe_code": None},
        ]
        p2 = [
            {"code": "B1", "type": "overall", "strand": "B", "topic": None,
             "description": "x", "parent_oe_code": None},
        ]
        diffs, consensus = ec.diff_passes(p1, p2)
        assert len(diffs) == 1
        assert diffs[0]["code"] == "B2"
        assert diffs[0]["kind"] == "missing_in_pass2"
        assert diffs[0]["pass2"] is None
        assert {c["code"] for c in consensus} == {"B1"}

    def test_missing_in_pass1_is_diff(self):
        p1 = [
            {"code": "B1", "type": "overall", "strand": "B", "topic": None,
             "description": "x", "parent_oe_code": None},
        ]
        p2 = [
            {"code": "B1", "type": "overall", "strand": "B", "topic": None,
             "description": "x", "parent_oe_code": None},
            {"code": "B2", "type": "overall", "strand": "B", "topic": None,
             "description": "y", "parent_oe_code": None},
        ]
        diffs, consensus = ec.diff_passes(p1, p2)
        assert len(diffs) == 1
        assert diffs[0]["code"] == "B2"
        assert diffs[0]["kind"] == "missing_in_pass1"
        assert diffs[0]["pass1"] is None

    def test_strand_mismatch_is_diff(self):
        p1 = [{"code": "B1", "type": "overall", "strand": "B: Number Sense",
               "topic": None, "description": "x", "parent_oe_code": None}]
        p2 = [{"code": "B1", "type": "overall", "strand": "C: Algebra",
               "topic": None, "description": "x", "parent_oe_code": None}]
        diffs, consensus = ec.diff_passes(p1, p2)
        assert len(diffs) == 1
        assert diffs[0]["kind"] == "field_mismatch"
        assert "strand" in diffs[0]["fields"]
        assert consensus == []

    def test_type_mismatch_is_diff(self):
        p1 = [{"code": "B1.1", "type": "specific", "strand": "B", "topic": None,
               "description": "x", "parent_oe_code": "B1"}]
        p2 = [{"code": "B1.1", "type": "overall", "strand": "B", "topic": None,
               "description": "x", "parent_oe_code": None}]
        diffs, _ = ec.diff_passes(p1, p2)
        assert len(diffs) == 1
        assert "type" in diffs[0]["fields"]
        assert "parent_oe_code" in diffs[0]["fields"]

    def test_parent_oe_mismatch_is_diff(self):
        p1 = [{"code": "B1.1", "type": "specific", "strand": "B", "topic": None,
               "description": "x", "parent_oe_code": "B1"}]
        p2 = [{"code": "B1.1", "type": "specific", "strand": "B", "topic": None,
               "description": "x", "parent_oe_code": "B2"}]
        diffs, _ = ec.diff_passes(p1, p2)
        assert len(diffs) == 1
        assert diffs[0]["fields"] == ["parent_oe_code"]

    def test_code_normalization_case_insensitive(self):
        p1 = [{"code": "b1", "type": "overall", "strand": "B", "topic": None,
               "description": "x", "parent_oe_code": None}]
        p2 = [{"code": "B1", "type": "overall", "strand": "B", "topic": None,
               "description": "x", "parent_oe_code": None}]
        diffs, consensus = ec.diff_passes(p1, p2)
        assert diffs == []
        assert len(consensus) == 1

    def test_items_without_code_are_skipped(self):
        p1 = [
            {"code": "B1", "type": "overall", "strand": "B", "topic": None,
             "description": "x", "parent_oe_code": None},
            {"code": None, "type": "overall", "strand": "?", "topic": None,
             "description": "no code", "parent_oe_code": None},
        ]
        p2 = [{"code": "B1", "type": "overall", "strand": "B", "topic": None,
               "description": "x", "parent_oe_code": None}]
        diffs, consensus = ec.diff_passes(p1, p2)
        # The code-less item is dropped from indexing entirely; no spurious diff
        assert diffs == []
        assert len(consensus) == 1


# ---------------------------------------------------------------------------
# PDF parsing — error handling for malformed input.
# ---------------------------------------------------------------------------


class TestParsePDF:
    def test_missing_file_raises_helpful_error(self, tmp_path: Path):
        with pytest.raises(ec.PDFExtractionError, match="PDF not found"):
            ec.parse_pdf(tmp_path / "nope.pdf")

    def test_directory_path_raises_helpful_error(self, tmp_path: Path):
        with pytest.raises(ec.PDFExtractionError, match="Not a file"):
            ec.parse_pdf(tmp_path)

    def test_empty_file_raises_helpful_error(self, tmp_path: Path):
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")
        with pytest.raises(ec.PDFExtractionError, match="PDF is empty"):
            ec.parse_pdf(empty)

    def test_malformed_pdf_raises_helpful_error(self, tmp_path: Path):
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"this is definitely not a PDF")
        with pytest.raises(ec.PDFExtractionError) as exc_info:
            ec.parse_pdf(bad)
        # Either "Malformed PDF" or "Failed to open PDF" depending on PyPDF2 version
        msg = str(exc_info.value)
        assert "PDF" in msg and str(bad) in msg

    def test_synthetic_fixture_parses_successfully(self):
        assert SYNTHETIC_PDF.exists(), f"Fixture missing: {SYNTHETIC_PDF}"
        parsed = ec.parse_pdf(SYNTHETIC_PDF)
        assert parsed.page_count == 2
        assert len(parsed.sha256) == 64  # sha256 hex digest
        # Synthetic PDF mentions B1, B2.3, C1, etc.
        assert "B1" in parsed.text
        assert "B2.3" in parsed.text
        assert "C1" in parsed.text


# ---------------------------------------------------------------------------
# Round-trip — run the extractor on the synthetic fixture with mocked Claude.
# ---------------------------------------------------------------------------


def _fake_pass1_response() -> str:
    """Realistic pass-1 output for the synthetic fixture."""
    return json.dumps([
        {"code": "B1", "type": "overall", "strand": "B: Number Sense",
         "topic": "Numbers", "description": "Understand numbers + relationships.",
         "parent_oe_code": None},
        {"code": "B2", "type": "overall", "strand": "B: Number Sense",
         "topic": "Operations", "description": "Apply operations.",
         "parent_oe_code": None},
        {"code": "B1.1", "type": "specific", "strand": "B: Number Sense",
         "topic": "Numbers", "description": "Read/order whole numbers.",
         "parent_oe_code": "B1"},
        {"code": "B1.2", "type": "specific", "strand": "B: Number Sense",
         "topic": "Numbers", "description": "Order decimals.",
         "parent_oe_code": "B1"},
        {"code": "B2.1", "type": "specific", "strand": "B: Number Sense",
         "topic": "Operations", "description": "Mental math.",
         "parent_oe_code": "B2"},
        {"code": "B2.2", "type": "specific", "strand": "B: Number Sense",
         "topic": "Operations", "description": "Multiply/divide.",
         "parent_oe_code": "B2"},
        {"code": "B2.3", "type": "specific", "strand": "B: Number Sense",
         "topic": "Operations", "description": "Fractions like denominators.",
         "parent_oe_code": "B2"},
        {"code": "C1", "type": "overall", "strand": "C: Algebra",
         "topic": "Patterns", "description": "Identify patterns.",
         "parent_oe_code": None},
        {"code": "C1.1", "type": "specific", "strand": "C: Algebra",
         "topic": "Patterns", "description": "Describe repeating patterns.",
         "parent_oe_code": "C1"},
        {"code": "C1.2", "type": "specific", "strand": "C: Algebra",
         "topic": "Patterns", "description": "Translate patterns.",
         "parent_oe_code": "C1"},
        {"code": "C1.3", "type": "specific", "strand": "C: Algebra",
         "topic": "Patterns", "description": "Pattern rules.",
         "parent_oe_code": "C1"},
    ])


def _fake_pass2_response() -> str:
    """Pass-2 with one missing item + one strand mismatch — to verify diffs."""
    return json.dumps([
        {"code": "B1", "type": "overall", "strand": "B: Number Sense",
         "topic": "Numbers", "description": "Numbers + their relationships.",
         "parent_oe_code": None},
        {"code": "B2", "type": "overall", "strand": "B: Number Sense",
         "topic": "Operations", "description": "Operations on numbers.",
         "parent_oe_code": None},
        {"code": "B1.1", "type": "specific", "strand": "B: Number Sense",
         "topic": "Numbers", "description": "Whole numbers ordering.",
         "parent_oe_code": "B1"},
        # B1.2 missing in pass2 → should appear as a diff
        {"code": "B2.1", "type": "specific", "strand": "B: Number Sense",
         "topic": "Operations", "description": "Mental addition.",
         "parent_oe_code": "B2"},
        {"code": "B2.2", "type": "specific", "strand": "B: Number Sense",
         "topic": "Operations", "description": "Three-digit division.",
         "parent_oe_code": "B2"},
        {"code": "B2.3", "type": "specific", "strand": "B: Number Sense",
         "topic": "Operations", "description": "Like-denominator fractions.",
         "parent_oe_code": "B2"},
        {"code": "C1", "type": "overall",
         # Strand wording differs → should appear as a field_mismatch diff
         "strand": "C: Patterns and Algebra",
         "topic": "Patterns", "description": "Growing/shrinking patterns.",
         "parent_oe_code": None},
        {"code": "C1.1", "type": "specific", "strand": "C: Patterns and Algebra",
         "topic": "Patterns", "description": "Repeating patterns.",
         "parent_oe_code": "C1"},
        {"code": "C1.2", "type": "specific", "strand": "C: Patterns and Algebra",
         "topic": "Patterns", "description": "Translate.",
         "parent_oe_code": "C1"},
        {"code": "C1.3", "type": "specific", "strand": "C: Patterns and Algebra",
         "topic": "Patterns", "description": "Rule extension.",
         "parent_oe_code": "C1"},
    ])


@pytest.mark.asyncio
async def test_extract_ceg_round_trip_with_mocked_claude(tmp_path: Path):
    """End-to-end: real PDF parsing + mocked Claude calls + diff + write."""
    out_path = tmp_path / "5-MATH-2020.pending.json"

    # Mock generate_content to return pass1 then pass2 on successive calls.
    responses = iter([
        (_fake_pass1_response(), "end_turn"),
        (_fake_pass2_response(), "end_turn"),
    ])

    async def fake_generate_content(*_args, **_kwargs):
        return next(responses)

    with patch("app.services.ai_service.generate_content", side_effect=fake_generate_content):
        result = await ec.extract_ceg(
            pdf_path=SYNTHETIC_PDF,
            grade=5,
            subject="MATH",
            ministry_version="2020",
        )

    # Output shape
    assert set(result.keys()) == {
        "pass1_output", "pass2_output", "diffs", "consensus", "metadata"
    }
    assert len(result["pass1_output"]) == 11
    assert len(result["pass2_output"]) == 10

    # Diff detection — B1.2 missing in pass2; C1, C1.1, C1.2, C1.3 strand mismatch
    diff_codes = {d["code"] for d in result["diffs"]}
    assert "B1.2" in diff_codes
    assert "C1" in diff_codes

    missing = [d for d in result["diffs"] if d["kind"] == "missing_in_pass2"]
    assert len(missing) == 1
    assert missing[0]["code"] == "B1.2"

    strand_diffs = [
        d for d in result["diffs"]
        if d["kind"] == "field_mismatch" and "strand" in d.get("fields", [])
    ]
    assert len(strand_diffs) >= 1

    # Consensus contains items where passes agreed (B1, B2, B1.1, B2.1-B2.3)
    consensus_codes = {c["code"] for c in result["consensus"]}
    assert "B1" in consensus_codes
    assert "B2.3" in consensus_codes

    # Metadata
    md = result["metadata"]
    assert md["grade"] == 5
    assert md["subject"] == "MATH"
    assert md["ministry_version"] == "2020"
    assert md["source_pdf_pages"] == 2
    assert len(md["source_pdf_sha256"]) == 64
    assert "extraction_date" in md
    assert "model" in md
    # Truncation tracking — synthetic fixture is well under 60K chars
    assert md["source_text_truncated"] is False
    assert md["source_text_chars"] > 0
    assert md["source_text_chars_used"] == md["source_text_chars"]

    # Round-trip write
    ec.write_output(result, out_path)
    assert out_path.exists()
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk["metadata"]["grade"] == 5
    assert len(on_disk["pass1_output"]) == 11


@pytest.mark.asyncio
async def test_run_pass_invokes_generate_content_with_correct_args():
    """Verify run_pass goes through app/services/ai_service.generate_content
    (not a direct anthropic SDK call) per CLAUDE.md."""
    captured: dict = {}

    async def fake_generate_content(prompt, system_prompt, max_tokens, temperature):
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        captured["max_tokens"] = max_tokens
        captured["temperature"] = temperature
        return ('[{"code": "B1", "type": "overall"}]', "end_turn")

    with patch("app.services.ai_service.generate_content", side_effect=fake_generate_content):
        items, _raw, truncated = await ec.run_pass(
            document_text="Strand B: Number Sense\nB1 ...",
            grade=5,
            subject="MATH",
            user_prompt_template=ec.PASS1_USER_PROMPT_TEMPLATE,
            system_prompt=ec.PASS1_SYSTEM_PROMPT,
        )

    assert items == [{"code": "B1", "type": "overall"}]
    assert truncated is False  # short input — no truncation
    assert captured["system_prompt"] == ec.PASS1_SYSTEM_PROMPT
    assert "Grade: 5" in captured["prompt"]
    assert "Subject: MATH" in captured["prompt"]
    assert "Strand B: Number Sense" in captured["prompt"]
    assert captured["max_tokens"] == ec.EXTRACTION_MAX_TOKENS
    # Low temperature for reproducible structured output
    assert captured["temperature"] == 0.1


# ---------------------------------------------------------------------------
# Truncation behaviour — silent truncation must surface in metadata.
# ---------------------------------------------------------------------------


class TestTruncation:
    def test_short_text_not_truncated(self):
        text, truncated = ec._truncate_for_prompt("hello", limit=100)
        assert truncated is False
        assert text == "hello"

    def test_long_text_is_truncated_and_flagged(self):
        long_text = "x" * 1000
        text, truncated = ec._truncate_for_prompt(long_text, limit=100)
        assert truncated is True
        assert len(text) == 100

    def test_text_exactly_at_limit_not_truncated(self):
        text, truncated = ec._truncate_for_prompt("y" * 50, limit=50)
        assert truncated is False
        assert len(text) == 50


@pytest.mark.asyncio
async def test_truncation_surfaces_in_metadata(tmp_path: Path, monkeypatch):
    """Force a tiny prompt cap so the synthetic fixture exceeds it; verify
    the truncation flag lands in metadata rather than silently failing."""
    # Lower the cap to force truncation on a short fixture.
    monkeypatch.setattr(ec, "MAX_PROMPT_CHARS", 50)

    responses = iter([
        ('[{"code": "B1", "type": "overall"}]', "end_turn"),
        ('[{"code": "B1", "type": "overall"}]', "end_turn"),
    ])

    async def fake_generate_content(*_args, **_kwargs):
        return next(responses)

    with patch("app.services.ai_service.generate_content", side_effect=fake_generate_content):
        result = await ec.extract_ceg(
            pdf_path=SYNTHETIC_PDF,
            grade=5,
            subject="MATH",
            ministry_version=None,
        )

    md = result["metadata"]
    assert md["source_text_truncated"] is True
    assert md["source_text_chars"] > md["source_text_chars_used"]
    assert md["source_text_chars_used"] == 50


# ---------------------------------------------------------------------------
# CLI argparse + main()
# ---------------------------------------------------------------------------


class TestCLIMain:
    def test_invalid_grade_returns_error(self, tmp_path: Path):
        rc = ec.main([
            "--pdf", str(SYNTHETIC_PDF),
            "--grade", "13",
            "--subject", "MATH",
            "--out", str(tmp_path / "out.json"),
        ])
        assert rc == 2

    def test_missing_pdf_returns_error(self, tmp_path: Path, capsys):
        rc = ec.main([
            "--pdf", str(tmp_path / "does-not-exist.pdf"),
            "--grade", "5",
            "--subject", "MATH",
            "--out", str(tmp_path / "out.json"),
        ])
        assert rc == 3
        err = capsys.readouterr().err
        assert "PDF" in err

    def test_main_round_trip_with_mocked_claude(self, tmp_path: Path, capsys):
        out_path = tmp_path / "out.json"
        responses = iter([
            (_fake_pass1_response(), "end_turn"),
            (_fake_pass2_response(), "end_turn"),
        ])

        async def fake_generate_content(*_args, **_kwargs):
            return next(responses)

        with patch("app.services.ai_service.generate_content", side_effect=fake_generate_content):
            rc = ec.main([
                "--pdf", str(SYNTHETIC_PDF),
                "--grade", "5",
                "--subject", "MATH",
                "--out", str(out_path),
                "--ministry-version", "2020",
            ])

        assert rc == 0
        assert out_path.exists()
        captured = capsys.readouterr().out
        assert "diffs=" in captured

        on_disk = json.loads(out_path.read_text(encoding="utf-8"))
        assert on_disk["metadata"]["grade"] == 5
        assert on_disk["metadata"]["subject"] == "MATH"
        assert on_disk["metadata"]["ministry_version"] == "2020"
