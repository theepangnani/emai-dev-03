"""TeachAssist file parser service.

Handles two import formats exported from teachassist.ca:
  1. XML — UnitPlan / LongRangePlan XML format
  2. CSV  — tabular format with TeachAssist-style column headers

Both parsers return a list of dicts compatible with LessonPlanCreate.
"""
import csv
import io
import json
import logging
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# XML parser
# ---------------------------------------------------------------------------

def _text(element: ET.Element | None) -> str | None:
    """Return stripped text content of an element, or None if missing."""
    if element is None:
        return None
    return (element.text or "").strip() or None


def _collect_expectation_codes(parent: ET.Element | None, tag: str = "Expectation") -> list[str]:
    """Collect code attributes from child Expectation elements."""
    if parent is None:
        return []
    codes = []
    for exp in parent.findall(tag):
        code = exp.get("code", "").strip()
        if code:
            codes.append(code)
        elif exp.text and exp.text.strip():
            codes.append(exp.text.strip())
    return codes


def _parse_unit_plan(root: ET.Element) -> list[dict[str, Any]]:
    """Parse a <UnitPlan> element into one or more lesson plan dicts."""
    plans: list[dict[str, Any]] = []

    title = _text(root.find("Title")) or "Untitled Unit Plan"
    grade_level = _text(root.find("GradeLevel"))
    subject_code = _text(root.find("SubjectCode"))
    strand = _text(root.find("Strand"))

    overall = _collect_expectation_codes(root.find("OverallExpectations"))
    specific = _collect_expectation_codes(root.find("SpecificExpectations"))

    # Combined for the curriculum_expectations field
    all_expectations = overall + specific

    # Big ideas
    big_ideas_el = root.find("BigIdeas")
    big_ideas: list[str] = []
    if big_ideas_el is not None:
        for idea in big_ideas_el.findall("Idea"):
            text = (idea.text or "").strip()
            if text:
                big_ideas.append(text)

    # Materials / resources
    materials_el = root.find("Materials")
    materials: list[str] = []
    if materials_el is not None:
        for item in materials_el.findall("Item"):
            text = (item.text or "").strip()
            if text:
                materials.append(text)

    # Start / end dates
    start_date = _text(root.find("StartDate"))
    end_date = _text(root.find("EndDate"))

    # Unit-level plan (the UP itself)
    unit_plan: dict[str, Any] = {
        "plan_type": "unit",
        "title": title,
        "grade_level": grade_level,
        "subject_code": subject_code,
        "strand": strand,
        "overall_expectations": overall,
        "specific_expectations": specific,
        "curriculum_expectations": all_expectations,
        "big_ideas": big_ideas,
        "materials_resources": materials,
        "start_date": start_date,
        "end_date": end_date,
        "imported_from": "teachassist",
    }
    plans.append(unit_plan)

    # Individual lessons within the unit
    lessons_el = root.find("Lessons")
    if lessons_el is not None:
        for idx, lesson_el in enumerate(lessons_el.findall("Lesson"), start=1):
            duration_str = lesson_el.get("duration", "")
            duration: int | None = None
            try:
                duration = int(duration_str) if duration_str else None
            except ValueError:
                pass

            # Learning goals
            learning_goals: list[str] = []
            for lg in lesson_el.findall("LearningGoal"):
                text = (lg.text or "").strip()
                if text:
                    learning_goals.append(text)

            # Success criteria
            success_criteria: list[str] = []
            for sc in lesson_el.findall("SuccessCriteria"):
                text = (sc.text or "").strip()
                if text:
                    success_criteria.append(text)

            # 3-part lesson
            minds_on = _text(lesson_el.find("MindsOn"))
            action = _text(lesson_el.find("Action"))
            consolidation = _text(lesson_el.find("Consolidation"))
            three_part: dict[str, str | None] | None = None
            if any([minds_on, action, consolidation]):
                three_part = {
                    "minds_on": minds_on,
                    "action": action,
                    "consolidation": consolidation,
                }

            # Assessment
            afl = _text(lesson_el.find("AssessmentForLearning"))
            aol = _text(lesson_el.find("AssessmentOfLearning"))

            # Differentiation
            diff_el = lesson_el.find("Differentiation")
            differentiation: dict[str, str | None] | None = None
            if diff_el is not None:
                differentiation = {
                    "enrichment": _text(diff_el.find("Enrichment")),
                    "support": _text(diff_el.find("Support")),
                    "ell": _text(diff_el.find("ELL")),
                }

            lesson_title = _text(lesson_el.find("Title")) or f"{title} — Lesson {idx}"

            daily_plan: dict[str, Any] = {
                "plan_type": "daily",
                "title": lesson_title,
                "grade_level": grade_level,
                "subject_code": subject_code,
                "strand": strand,
                "overall_expectations": overall,
                "specific_expectations": specific,
                "curriculum_expectations": all_expectations,
                "learning_goals": learning_goals,
                "success_criteria": success_criteria,
                "three_part_lesson": three_part,
                "assessment_for_learning": afl,
                "assessment_of_learning": aol,
                "differentiation": differentiation,
                "duration_minutes": duration,
                "imported_from": "teachassist",
            }
            plans.append(daily_plan)

    return plans


def _parse_long_range_plan(root: ET.Element) -> list[dict[str, Any]]:
    """Parse a <LongRangePlan> element."""
    title = _text(root.find("Title")) or "Untitled Long-Range Plan"
    grade_level = _text(root.find("GradeLevel"))
    subject_code = _text(root.find("SubjectCode"))

    overall = _collect_expectation_codes(root.find("OverallExpectations"))

    lrp: dict[str, Any] = {
        "plan_type": "long_range",
        "title": title,
        "grade_level": grade_level,
        "subject_code": subject_code,
        "overall_expectations": overall,
        "curriculum_expectations": overall,
        "imported_from": "teachassist",
    }

    plans: list[dict[str, Any]] = [lrp]

    # Embedded unit plans
    for unit_el in root.findall("UnitPlan"):
        plans.extend(_parse_unit_plan(unit_el))

    return plans


def parse_teachassist_xml(content: bytes) -> list[dict[str, Any]]:
    """Parse TeachAssist XML export into a list of LessonPlanCreate-compatible dicts.

    Handles both <UnitPlan> and <LongRangePlan> root elements, as well as
    wrapper elements that contain one or more of those children.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logger.warning("TeachAssist XML parse error: %s", exc)
        raise ValueError(f"Invalid XML: {exc}") from exc

    plans: list[dict[str, Any]] = []
    tag = root.tag

    if tag == "UnitPlan":
        plans.extend(_parse_unit_plan(root))
    elif tag == "LongRangePlan":
        plans.extend(_parse_long_range_plan(root))
    else:
        # Wrapper element — scan children
        for child in root:
            if child.tag == "UnitPlan":
                plans.extend(_parse_unit_plan(child))
            elif child.tag == "LongRangePlan":
                plans.extend(_parse_long_range_plan(child))
            elif child.tag == "Lesson":
                # Bare lesson list
                plans.extend(_parse_unit_plan(root))
                break

    if not plans:
        # Fall back: treat root as unit plan
        plans.extend(_parse_unit_plan(root))

    logger.info("TeachAssist XML: parsed %d plan(s)", len(plans))
    return plans


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------

# Canonical column name mapping (case-insensitive, strip spaces)
_CSV_COLUMN_MAP: dict[str, str] = {
    "title": "title",
    "plan_type": "plan_type",
    "plantype": "plan_type",
    "type": "plan_type",
    "grade": "grade_level",
    "gradelevel": "grade_level",
    "grade_level": "grade_level",
    "subject": "subject_code",
    "subjectcode": "subject_code",
    "subject_code": "subject_code",
    "strand": "strand",
    "unit": "unit_number",
    "unit_number": "unit_number",
    "unitnumber": "unit_number",
    "duration": "duration_minutes",
    "duration_minutes": "duration_minutes",
    "durationminutes": "duration_minutes",
    "learninggoals": "learning_goals",
    "learning_goals": "learning_goals",
    "successcriteria": "success_criteria",
    "success_criteria": "success_criteria",
    "overallexpectations": "overall_expectations",
    "overall_expectations": "overall_expectations",
    "specificexpectations": "specific_expectations",
    "specific_expectations": "specific_expectations",
    "curriculumexpectations": "curriculum_expectations",
    "curriculum_expectations": "curriculum_expectations",
    "bigideas": "big_ideas",
    "big_ideas": "big_ideas",
    "mindson": "minds_on",
    "minds_on": "minds_on",
    "action": "action",
    "consolidation": "consolidation",
    "assessmentforlearning": "assessment_for_learning",
    "assessment_for_learning": "assessment_for_learning",
    "assessmentoflearning": "assessment_of_learning",
    "assessment_of_learning": "assessment_of_learning",
    "enrichment": "enrichment",
    "support": "support",
    "ell": "ell",
    "materials": "materials_resources",
    "materials_resources": "materials_resources",
    "materialsresources": "materials_resources",
    "crosscurricular": "cross_curricular",
    "cross_curricular": "cross_curricular",
    "startdate": "start_date",
    "start_date": "start_date",
    "enddate": "end_date",
    "end_date": "end_date",
    "istemplate": "is_template",
    "is_template": "is_template",
    "template": "is_template",
}

# Fields that hold pipe/semicolon/newline-delimited lists
_LIST_FIELDS = {
    "big_ideas",
    "curriculum_expectations",
    "overall_expectations",
    "specific_expectations",
    "learning_goals",
    "success_criteria",
    "materials_resources",
    "cross_curricular",
}

_THREE_PART_FIELDS = {"minds_on", "action", "consolidation"}
_DIFF_FIELDS = {"enrichment", "support", "ell"}


def _split_list(value: str) -> list[str]:
    """Split a pipe, semicolon, or newline-delimited list value."""
    if not value:
        return []
    for sep in ("|", ";", "\n"):
        if sep in value:
            return [v.strip() for v in value.split(sep) if v.strip()]
    return [value.strip()] if value.strip() else []


def parse_teachassist_csv(content: bytes) -> list[dict[str, Any]]:
    """Parse a TeachAssist-style CSV export into LessonPlanCreate-compatible dicts.

    Column names are matched case-insensitively. List fields may use | or ;
    as delimiters. Three-part lesson fields (MindsOn, Action, Consolidation)
    are assembled into a nested dict.
    """
    try:
        text = content.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV file has no header row")

    # Build normalised header → canonical field mapping
    header_map: dict[str, str] = {}
    for raw_header in reader.fieldnames:
        normalised = raw_header.strip().lower().replace(" ", "").replace("-", "_")
        canonical = _CSV_COLUMN_MAP.get(normalised)
        if canonical:
            header_map[raw_header] = canonical

    plans: list[dict[str, Any]] = []

    for row_num, raw_row in enumerate(reader, start=2):
        plan: dict[str, Any] = {
            "imported_from": "teachassist",
            "plan_type": "unit",  # default
        }
        three_part: dict[str, str | None] = {}
        differentiation: dict[str, str | None] = {}

        for raw_col, canonical in header_map.items():
            value = (raw_row.get(raw_col) or "").strip()
            if not value:
                continue

            if canonical in _LIST_FIELDS:
                plan[canonical] = _split_list(value)
            elif canonical in _THREE_PART_FIELDS:
                three_part[canonical] = value
            elif canonical in _DIFF_FIELDS:
                differentiation[canonical] = value
            elif canonical == "duration_minutes":
                try:
                    plan[canonical] = int(value)
                except ValueError:
                    logger.debug("Row %d: invalid duration '%s'", row_num, value)
            elif canonical == "unit_number":
                try:
                    plan[canonical] = int(value)
                except ValueError:
                    logger.debug("Row %d: invalid unit_number '%s'", row_num, value)
            elif canonical == "is_template":
                plan[canonical] = value.lower() in ("1", "true", "yes")
            else:
                plan[canonical] = value

        if three_part:
            plan["three_part_lesson"] = three_part
        if differentiation:
            plan["differentiation"] = differentiation

        if "title" not in plan or not plan["title"]:
            logger.debug("Row %d: skipping row with no title", row_num)
            continue

        plans.append(plan)

    logger.info("TeachAssist CSV: parsed %d plan(s)", len(plans))
    return plans


# ---------------------------------------------------------------------------
# JSON serialisation helpers used by the API layer
# ---------------------------------------------------------------------------

def serialise_list_field(value: list[str] | None) -> str | None:
    """Convert a Python list to a JSON string for storage."""
    if value is None:
        return None
    return json.dumps(value)


def deserialise_list_field(value: str | None) -> list[str]:
    """Convert a stored JSON string back to a Python list."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def serialise_dict_field(value: dict | None) -> str | None:
    """Convert a Python dict to a JSON string for storage."""
    if value is None:
        return None
    return json.dumps(value)


def deserialise_dict_field(value: str | None) -> dict | None:
    """Convert a stored JSON string back to a Python dict."""
    if not value:
        return None
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None
