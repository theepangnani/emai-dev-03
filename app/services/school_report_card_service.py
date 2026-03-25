"""
AI service layer for School Report Card Upload & Analysis (#2286).

Provides:
- analyze_report_card()  — AI-powered report card analysis
- generate_career_path() — career path suggestions from multi-term data
- extract_metadata()     — regex-based metadata extraction (no AI)
- compute_content_hash() — SHA-256 dedup hash
"""
import hashlib
import json
import re

from app.core.logging_config import get_logger
from app.services.ai_service import generate_content, get_last_ai_usage  # noqa: F401

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from AI response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _safe_parse_json(raw: str, fallback_key: str = "raw_text") -> dict:
    """Parse JSON from AI response, returning a minimal wrapper on failure."""
    try:
        cleaned = _strip_markdown_fences(raw)
        return json.loads(cleaned)
    except (json.JSONDecodeError, IndexError, ValueError):
        logger.warning("Failed to parse AI JSON response, wrapping raw text")
        return {fallback_key: raw[:3000]}


# ---------------------------------------------------------------------------
# 1. Report Card Analysis
# ---------------------------------------------------------------------------

_REPORT_CARD_SYSTEM_PROMPT = (
    "You are an Ontario education specialist with deep expertise in the Ontario "
    "curriculum and provincial report card formats.\n\n"
    "You understand Ontario Achievement Levels:\n"
    "- Level 4 (80-100%): exceeds the provincial standard\n"
    "- Level 3 (70-79%): meets the provincial standard\n"
    "- Level 2 (60-69%): approaching the provincial standard\n"
    "- Level 1 (50-59%): below the provincial standard\n\n"
    "You understand Ontario Learning Skills ratings:\n"
    "- E (Excellent), G (Good), S (Satisfactory), N (Needs Improvement)\n\n"
    "You handle both elementary (Grades 1-8) and secondary (Grades 9-12) report "
    "card formats. You know that secondary interim reports may only include "
    "achievement levels without percentages or detailed teacher comments.\n\n"
    "Always provide factual, supportive, and actionable analysis for parents. "
    "Never fabricate grades or comments that are not present in the source text."
)


async def analyze_report_card(
    text_content: str,
    student_name: str,
    grade_level: str | None = None,
    school_name: str | None = None,
    term: str | None = None,
) -> dict:
    """
    Analyze report card text using AI and return structured analysis.

    Args:
        text_content: The full extracted text from the report card PDF/image.
        student_name: Student's name for context.
        grade_level: e.g. "08", "10".
        school_name: School name if known.
        term: e.g. "Term 1", "Semester Two Interim".

    Returns:
        Dict with keys: teacher_feedback_summary, grade_analysis, learning_skills,
        improvement_areas, parent_tips, overall_summary.
    """
    logger.info(
        "Analyzing report card | student=%s | grade=%s | school=%s | term=%s",
        student_name, grade_level, school_name, term,
    )

    context_parts = [f"Student: {student_name}"]
    if grade_level:
        context_parts.append(f"Grade: {grade_level}")
    if school_name:
        context_parts.append(f"School: {school_name}")
    if term:
        context_parts.append(f"Term: {term}")
    context_block = "\n".join(context_parts)

    prompt = f"""Analyze the following Ontario report card and provide a structured analysis for the parent.

**Student Context:**
{context_block}

**Report Card Text:**
{text_content}

Respond with a JSON object in this exact structure:
{{
  "teacher_feedback_summary": "Consolidated 2-3 paragraph narrative summarizing all teacher comments across subjects. Highlight recurring themes, praise, and concerns.",
  "grade_analysis": [
    {{
      "subject": "Mathematics",
      "grade": "71%",
      "median": "84%",
      "level": 2,
      "teacher_comment": "exact quote from the report card if available",
      "feedback": "AI analysis of performance, comparison to median if available, strengths and gaps identified"
    }}
  ],
  "learning_skills": {{
    "ratings": [
      {{"skill": "Responsibility", "rating": "G"}},
      {{"skill": "Organization", "rating": "G"}},
      {{"skill": "Independent Work", "rating": "S"}},
      {{"skill": "Collaboration", "rating": "G"}},
      {{"skill": "Initiative", "rating": "S"}},
      {{"skill": "Self-Regulation", "rating": "G"}}
    ],
    "summary": "Overall assessment of learning skills patterns and what they indicate"
  }},
  "improvement_areas": [
    {{
      "area": "Math — Metric Conversions",
      "detail": "Specific guidance on what the student should work on and how",
      "priority": "high"
    }}
  ],
  "parent_tips": [
    {{
      "tip": "Practice metric conversions using cooking measurements at home — converting mL to L when following recipes.",
      "related_subject": "Mathematics"
    }}
  ],
  "overall_summary": "Holistic 2-3 sentence assessment of the student's overall performance and trajectory"
}}

Rules:
- Only include subjects that appear in the report card text
- Use exact quotes for teacher_comment when available; set to null if no comment found
- For grade, use the percentage if available; otherwise use the achievement level (e.g. "Level 3")
- Set median to null if not present in the report
- Priority for improvement_areas: "high" (below Level 2 or significant concern), "medium" (Level 2 or minor gaps), "low" (small refinements)
- Parent tips should be practical, home-based activities
- If learning skills are not present in the report, set ratings to an empty list
- Return ONLY the JSON object, no other text"""

    try:
        raw, _ = await generate_content(
            prompt,
            system_prompt=_REPORT_CARD_SYSTEM_PROMPT,
            max_tokens=3000,
            temperature=0.3,
        )
    except Exception:
        logger.exception("AI call failed during report card analysis")
        raise

    result = _safe_parse_json(raw)
    logger.info("Report card analysis completed | subjects=%d", len(result.get("grade_analysis", [])))
    return result


# ---------------------------------------------------------------------------
# 2. Career Path Generation
# ---------------------------------------------------------------------------

_CAREER_PATH_SYSTEM_PROMPT = (
    "You are an Ontario education and career guidance specialist. You understand "
    "Ontario secondary school course codes (e.g., MPM2D, SNC1D, TGJ1O) and the "
    "pathways system (Academic, Applied, Open, University, College, Workplace). "
    "You provide thoughtful, evidence-based career suggestions grounded in the "
    "student's actual academic data. Be encouraging but realistic."
)


async def generate_career_path(
    analyses: list[dict],
    student_name: str,
    grade_level: str | None = None,
) -> dict:
    """
    Generate career path suggestions from multiple report card analyses.

    Args:
        analyses: List of previously generated analysis dicts (each containing
                  grade_analysis sections from analyze_report_card).
        student_name: Student's name.
        grade_level: Current grade level.

    Returns:
        Dict with keys: strengths, grade_trends, career_suggestions,
        overall_assessment.
    """
    logger.info(
        "Generating career path | student=%s | grade=%s | analyses_count=%d",
        student_name, grade_level, len(analyses),
    )

    # Build a summary of all grade data across analyses
    grade_data_lines = []
    for i, analysis in enumerate(analyses, 1):
        grade_data_lines.append(f"--- Report {i} ---")
        for entry in analysis.get("grade_analysis", []):
            subject = entry.get("subject", "Unknown")
            grade = entry.get("grade", "N/A")
            level = entry.get("level", "")
            feedback = entry.get("feedback", "")
            grade_data_lines.append(
                f"  {subject}: {grade} (Level {level}) — {feedback}"
            )
        # Include learning skills if present
        skills = analysis.get("learning_skills", {})
        if skills.get("ratings"):
            ratings_str = ", ".join(
                f"{r['skill']}: {r['rating']}" for r in skills["ratings"]
            )
            grade_data_lines.append(f"  Learning Skills: {ratings_str}")

    grade_data_block = "\n".join(grade_data_lines)

    context = f"Student: {student_name}"
    if grade_level:
        context += f"\nCurrent Grade: {grade_level}"

    prompt = f"""Based on the following academic data across multiple report cards, identify patterns and suggest career paths.

**{context}**

**Academic Data:**
{grade_data_block}

Respond with a JSON object in this exact structure:
{{
  "strengths": ["Visual Arts (consistently 85%+)", "Music", "English — Creative Writing"],
  "grade_trends": [
    {{
      "subject": "Mathematics",
      "trajectory": "declining",
      "data": "78% → 71% → 71%",
      "note": "Below median consistently — may need additional support"
    }}
  ],
  "career_suggestions": [
    {{
      "career": "UX/UI Design",
      "reasoning": "Strong performance in visual arts and technology suggests aptitude for design-oriented careers...",
      "related_subjects": ["Visual Arts", "Science/Technology"],
      "next_steps": "Consider TGJ1O Communications Technology in Grade 9 to explore digital design"
    }}
  ],
  "overall_assessment": "2-3 sentence holistic assessment of the student's academic trajectory and potential"
}}

Rules:
- Suggest 3-5 career paths with clear reasoning tied to the data
- trajectory values: "improving", "stable", "declining", or "new" (only one data point)
- Include Ontario course codes in next_steps where relevant
- Strengths should reference actual performance data
- Be encouraging — frame weaknesses as areas for growth, not limitations
- Return ONLY the JSON object, no other text"""

    try:
        raw, _ = await generate_content(
            prompt,
            system_prompt=_CAREER_PATH_SYSTEM_PROMPT,
            max_tokens=2000,
            temperature=0.5,
        )
    except Exception:
        logger.exception("AI call failed during career path generation")
        raise

    result = _safe_parse_json(raw)
    logger.info(
        "Career path generation completed | suggestions=%d",
        len(result.get("career_suggestions", [])),
    )
    return result


# ---------------------------------------------------------------------------
# 3. Metadata Extraction (regex, no AI)
# ---------------------------------------------------------------------------

def extract_metadata(text_content: str) -> dict:
    """
    Extract metadata from report card text using regex patterns.

    Returns dict with keys: student_name, grade_level, school_name, term,
    report_date, school_year, board_name. All values are optional (None if
    not found).
    """
    result: dict[str, str | None] = {
        "student_name": None,
        "grade_level": None,
        "school_name": None,
        "term": None,
        "report_date": None,
        "school_year": None,
        "board_name": None,
    }

    if not text_content:
        return result

    # Grade: "Grade: 08", "Grade: 10", "Grade 8"
    grade_match = re.search(
        r"Grade[:\s]+(\d{1,2})", text_content, re.IGNORECASE
    )
    if grade_match:
        result["grade_level"] = grade_match.group(1).lstrip("0") or "0"

    # School: "School: Franklin Street Public School", "School Name: ..."
    school_match = re.search(
        r"School(?:\s+Name)?[:\s]+([A-Z][A-Za-z\s.'-]+(?:School|Academy|Institute|Collegiate))",
        text_content,
    )
    if school_match:
        result["school_name"] = school_match.group(1).strip()

    # Date: "Date: 02/19/2026", "Report Issue date: March 9, 2026"
    # Try MM/DD/YYYY first
    date_match = re.search(
        r"(?:Date|Report\s+Issue\s+date)[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
        text_content,
        re.IGNORECASE,
    )
    if date_match:
        result["report_date"] = date_match.group(1).strip()
    else:
        # Try "Month Day, Year" format
        date_match = re.search(
            r"(?:Date|Report\s+Issue\s+date)[:\s]+"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text_content,
            re.IGNORECASE,
        )
        if date_match:
            result["report_date"] = date_match.group(1).strip()

    # Term: "Term 1", "Midterm", "Progress Report", "Semester Two Interim"
    term_match = re.search(
        r"(Term\s+\d|Midterm|Progress\s+Report|Semester\s+(?:One|Two|1|2)\s*(?:Interim|Final)?|"
        r"Final\s+Report\s+Card|Interim\s+Report)",
        text_content,
        re.IGNORECASE,
    )
    if term_match:
        result["term"] = term_match.group(1).strip()

    # Student name: "Student: Lastname, Firstname" or "Student Name: ..."
    student_match = re.search(
        r"Student(?:\s+Name)?[:\s]+([A-Za-z'-]+(?:,\s*[A-Za-z'-]+)?)",
        text_content,
        re.IGNORECASE,
    )
    if student_match:
        name = student_match.group(1).strip()
        # If "Last, First" format, flip it
        if "," in name:
            parts = [p.strip() for p in name.split(",", 1)]
            name = f"{parts[1]} {parts[0]}"
        result["student_name"] = name

    # School year: extract from date or semester references
    # Look for patterns like "2025-2026", "2025/2026"
    year_match = re.search(r"(20\d{2})\s*[-/]\s*(20\d{2})", text_content)
    if year_match:
        result["school_year"] = f"{year_match.group(1)}-{year_match.group(2)}"
    elif result["report_date"]:
        # Infer from report date — extract the year
        year_in_date = re.search(r"(20\d{2})", result["report_date"])
        if year_in_date:
            year = int(year_in_date.group(1))
            # Ontario school year runs Sep-Jun: dates Jan-Aug belong to the
            # school year that started the previous September
            month_match = re.search(
                r"(0?[1-8])/|"
                r"(?:January|February|March|April|May|June|July|August)",
                result["report_date"],
                re.IGNORECASE,
            )
            if month_match:
                result["school_year"] = f"{year - 1}-{year}"
            else:
                result["school_year"] = f"{year}-{year + 1}"

    # Board: look for known Ontario board name patterns
    board_match = re.search(
        r"((?:York|Toronto|Peel|Durham|Halton|Ottawa|Hamilton|Waterloo|Simcoe|Niagara)"
        r"(?:\s+Region)?\s+District\s+School\s+Board|"
        r"(?:York|Toronto|Halton|Dufferin-Peel|Durham|Ottawa|Hamilton-Wentworth|Waterloo|Simcoe Muskoka)"
        r"\s+Catholic\s+District\s+School\s+Board)",
        text_content,
        re.IGNORECASE,
    )
    if board_match:
        result["board_name"] = board_match.group(1).strip()

    logger.debug(
        "Extracted metadata | grade=%s | school=%s | term=%s | date=%s",
        result["grade_level"], result["school_name"], result["term"], result["report_date"],
    )
    return result


# ---------------------------------------------------------------------------
# 4. Content Hash
# ---------------------------------------------------------------------------

def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of text content for cache deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
