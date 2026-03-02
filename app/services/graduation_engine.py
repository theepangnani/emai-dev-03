"""Ontario OSSD Graduation Requirements Engine (#502).

Validates academic plans against OSSD rules:
  - 30 total credits (18 compulsory + 12 optional)
  - Specific compulsory requirements by subject area and grade

Public API:
  validate_plan(plan_courses)          -> ValidationResult
  check_prerequisites(course_code, ...) -> (bool, str | None)
  suggest_missing_compulsory(plan_courses) -> list[str]
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# OSSD Constants
# ---------------------------------------------------------------------------

OSSD_TOTAL_CREDITS = 30
OSSD_COMPULSORY_CREDITS = 18  # Minimum compulsory
OSSD_ELECTIVE_CREDITS = 12    # Minimum optional

# Compulsory requirement definitions.
# Each entry maps a canonical subject-area label to its requirements.
# "required"  — number of credits
# "grades"    — which grade levels satisfy the requirement (optional)
# "grade"     — single grade level (optional, alias for grades=[grade])
# "note"      — human-readable clarification shown in messages (optional)
OSSD_COMPULSORY: dict[str, dict] = {
    "English": {
        "required": 4,
        "grades": [9, 10, 11, 12],
        "note": "One English credit per grade (9-12)",
    },
    "Math": {
        "required": 3,
        "grades": [9, 10, 11],
        "note": "Must include a Grade 11 or 12 Math course",
    },
    "Science": {
        "required": 2,
        "grades": [9, 10],
    },
    "Canadian History": {
        "required": 1,
        "grade": 10,
    },
    "Canadian Geography": {
        "required": 1,
        "grade": 9,
    },
    "Arts": {
        "required": 1,
    },
    "Health & PE": {
        "required": 1,
    },
    "Civics": {
        "required": 0.5,
        "note": "Typically paired with Career Studies (CHV2O)",
    },
    "Career Studies": {
        "required": 0.5,
        "note": "Typically paired with Civics (GLC2O)",
    },
    "French": {
        "required": 1,
        "note": "FSF or equivalent",
    },
}

# ---------------------------------------------------------------------------
# Known prerequisite chains.
# Maps course_code -> list of acceptable prerequisite course codes
# (any ONE of the listed codes satisfies the prerequisite).
# Kept minimal; the catalog lookup fills in more detail when available.
# ---------------------------------------------------------------------------
_BUILTIN_PREREQUISITES: dict[str, list[str]] = {
    # Mathematics
    "MPM2D": ["MPM1D", "MFM1P"],
    "MFM2P": ["MPM1D", "MFM1P"],
    "MCR3U": ["MPM2D"],
    "MBF3C": ["MFM2P"],
    "MCF3M": ["MPM2D", "MFM2P"],
    "MAP4C": ["MBF3C", "MCF3M"],
    "MHF4U": ["MCR3U"],
    "MCV4U": ["MHF4U"],
    "MDM4U": ["MCR3U", "MCF3M"],
    "MEL4E": ["MEL3E"],
    # Science
    "SNC2D": ["SNC1D", "SNC1P"],
    "SNC2P": ["SNC1D", "SNC1P"],
    "SCH3U": ["SNC2D"],
    "SCH3C": ["SNC2D", "SNC2P"],
    "SBI3U": ["SNC2D"],
    "SPH3U": ["SNC2D"],
    "SCH4U": ["SCH3U"],
    "SBI4U": ["SBI3U"],
    "SPH4U": ["SPH3U"],
    # English
    "ENG2D": ["ENG1D", "ENG1P"],
    "ENG2P": ["ENG1D", "ENG1P"],
    "ENG3U": ["ENG2D"],
    "ENG3C": ["ENG2D", "ENG2P"],
    "ENG4U": ["ENG3U"],
    "ENG4C": ["ENG3C", "ENG3U"],
    # French
    "FSF2D": ["FSF1D", "FSF1P"],
    "FSF3U": ["FSF2D"],
    "FSF4U": ["FSF3U"],
}

# ---------------------------------------------------------------------------
# Compulsory category keyword mappings (subject area -> OSSD_COMPULSORY key)
# Used when plan_course.compulsory_category is not explicitly set.
# ---------------------------------------------------------------------------
_SUBJECT_TO_COMPULSORY: dict[str, str] = {
    "english": "English",
    "mathematics": "Math",
    "math": "Math",
    "science": "Science",
    "canadian history": "Canadian History",
    "history": "Canadian History",
    "canadian geography": "Canadian Geography",
    "geography": "Canadian Geography",
    "arts": "Arts",
    "visual arts": "Arts",
    "music": "Arts",
    "drama": "Arts",
    "dance": "Arts",
    "health and physical education": "Health & PE",
    "health & pe": "Health & PE",
    "physical education": "Health & PE",
    "civics": "Civics",
    "career studies": "Career Studies",
    "career education": "Career Studies",
    "french": "French",
    "french as a second language": "French",
}

# Course code prefix -> compulsory category (fallback when subject_area not set)
_CODE_PREFIX_TO_COMPULSORY: dict[str, str] = {
    "ENG": "English",
    "MPM": "Math",
    "MFM": "Math",
    "MCR": "Math",
    "MBF": "Math",
    "MCF": "Math",
    "MAP": "Math",
    "MHF": "Math",
    "MCV": "Math",
    "MDM": "Math",
    "MEL": "Math",
    "SNC": "Science",
    "SCH": "Science",
    "SBI": "Science",
    "SPH": "Science",
    "SES": "Science",
    "CHC": "Canadian History",
    "CGC": "Canadian Geography",
    "AVI": "Arts",
    "AMU": "Arts",
    "ADA": "Arts",
    "PPL": "Health & PE",
    "PAF": "Health & PE",
    "CHV": "Civics",
    "GLC": "Career Studies",
    "FSF": "French",
    "FIF": "French",
    "FEF": "French",
}


# ---------------------------------------------------------------------------
# ValidationResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    is_valid: bool
    total_credits: float
    compulsory_credits: float
    elective_credits: float
    completion_pct: float                       # 0-100
    missing_requirements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fulfilled_requirements: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_compulsory_category(course_code: str, subject_area: str | None, explicit_category: str | None) -> str | None:
    """Determine which OSSD compulsory category (if any) a course satisfies."""
    if explicit_category and explicit_category in OSSD_COMPULSORY:
        return explicit_category
    if subject_area:
        sa_lower = subject_area.lower()
        for keyword, category in _SUBJECT_TO_COMPULSORY.items():
            if keyword in sa_lower:
                return category
    # Fallback: course code prefix
    prefix = course_code[:3].upper() if course_code else ""
    return _CODE_PREFIX_TO_COMPULSORY.get(prefix)


def _grade_satisfies(grade_level: int, requirement: dict) -> bool:
    """Check whether a course's grade_level satisfies a requirement's grade constraints."""
    if "grade" in requirement:
        return grade_level == requirement["grade"]
    if "grades" in requirement:
        return grade_level in requirement["grades"]
    return True  # No grade constraint — any grade satisfies


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_plan(plan_courses: list) -> ValidationResult:
    """Validate a list of PlanCourse objects against OSSD graduation requirements.

    Args:
        plan_courses: list of PlanCourse ORM objects (or any object with the
                      same attributes: course_code, course_name, grade_level,
                      credit_value, status, is_compulsory, compulsory_category,
                      subject_area).

    Returns:
        ValidationResult with full breakdown.
    """
    # Only count courses that have not been dropped
    active_courses = [pc for pc in plan_courses if pc.status != "dropped"]

    # Accumulate credit totals
    total_credits = sum(pc.credit_value for pc in active_courses)

    # Bucket each course into its compulsory category (if any)
    # compulsory_bucket: category -> list of (grade_level, credit_value) tuples
    compulsory_bucket: dict[str, list[tuple[int, float]]] = {k: [] for k in OSSD_COMPULSORY}

    for pc in active_courses:
        cat = _resolve_compulsory_category(pc.course_code, getattr(pc, "subject_area", None), getattr(pc, "compulsory_category", None))
        if cat and cat in compulsory_bucket:
            compulsory_bucket[cat].append((pc.grade_level, pc.credit_value))

    # Compute fulfilled compulsory credits
    compulsory_credits = 0.0
    fulfilled: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []

    for category, req in OSSD_COMPULSORY.items():
        required_credits = req["required"]
        entries = compulsory_bucket[category]

        # Filter by grade constraints
        valid_entries = [
            (g, c) for (g, c) in entries if _grade_satisfies(g, req)
        ]
        earned = sum(c for _, c in valid_entries)
        note = req.get("note", "")

        if earned >= required_credits:
            fulfilled.append(f"{category} \u2713 ({earned:.1g} of {required_credits:.1g} credits)")
            compulsory_credits += required_credits
        else:
            shortfall = required_credits - earned
            grade_hint = ""
            if "grade" in req:
                grade_hint = f" (Grade {req['grade']})"
            elif "grades" in req:
                grade_hint = f" (Grades {', '.join(str(g) for g in req['grades'])})"
            msg = f"{category}{grade_hint}: need {required_credits:.1g} credit(s), have {earned:.1g}"
            if note:
                msg += f" — {note}"
            missing.append(msg)
            compulsory_credits += earned  # Partial credit still earned

    # Elective credits = total - compulsory earned (cap at what's needed)
    elective_credits = max(0.0, total_credits - compulsory_credits)

    # Check total credit threshold
    if total_credits < OSSD_TOTAL_CREDITS:
        missing.append(
            f"Total credits: need {OSSD_TOTAL_CREDITS}, have {total_credits:.1g}"
        )

    # Warnings (not hard failures but good-to-know)
    if not any(pc.course_code.startswith("MHF") or pc.course_code.startswith("MCV") for pc in active_courses):
        has_u_math = any(
            cat in ("Math",) and pc.pathway in ("U", "M")
            for pc in active_courses
            for cat in [_resolve_compulsory_category(pc.course_code, getattr(pc, "subject_area", None), None) or ""]
        )
        if not has_u_math:
            warnings.append("No University-level Math (U/M pathway) beyond Grade 10 — consider for university admission")

    # Check for Grade 11/12 English gap
    has_senior_english = any(
        _resolve_compulsory_category(pc.course_code, getattr(pc, "subject_area", None), None) == "English"
        and pc.grade_level in (11, 12)
        for pc in active_courses
    )
    if not has_senior_english:
        warnings.append("No Grade 11 or 12 English course planned — required for most university/college programs")

    # Compute completion percentage
    # Weight: 30 total credits = 100%
    completion_pct = min(100.0, round(total_credits / OSSD_TOTAL_CREDITS * 100, 1))

    is_valid = len(missing) == 0

    return ValidationResult(
        is_valid=is_valid,
        total_credits=round(total_credits, 2),
        compulsory_credits=round(compulsory_credits, 2),
        elective_credits=round(elective_credits, 2),
        completion_pct=completion_pct,
        missing_requirements=missing,
        warnings=warnings,
        fulfilled_requirements=fulfilled,
    )


def check_prerequisites(
    course_code: str,
    completed_courses: list[str],
    catalog_lookup: dict,
) -> tuple[bool, str | None]:
    """Check whether prerequisites are satisfied for a course.

    Args:
        course_code:       The course the student wants to take (e.g. "MCR3U").
        completed_courses: List of course codes the student has completed.
        catalog_lookup:    Dict mapping course_code -> catalog item dict
                           (expected key: "prerequisites" -> list[str]).

    Returns:
        (can_take: bool, reason: str | None)
        reason is None when can_take is True.
    """
    # Check catalog first, fall back to built-in
    prereqs: list[str] = []

    catalog_item = catalog_lookup.get(course_code.upper())
    if catalog_item and catalog_item.get("prerequisites"):
        prereqs = catalog_item["prerequisites"]
    elif course_code.upper() in _BUILTIN_PREREQUISITES:
        prereqs = _BUILTIN_PREREQUISITES[course_code.upper()]

    if not prereqs:
        return True, None  # No prerequisites defined

    completed_upper = {c.upper() for c in completed_courses}
    satisfied = any(p.upper() in completed_upper for p in prereqs)

    if not satisfied:
        prereq_list = " or ".join(prereqs)
        return False, f"{course_code} requires one of: {prereq_list}"

    return True, None


def suggest_missing_compulsory(plan_courses: list) -> list[str]:
    """Return a list of compulsory course codes that are not yet in the plan.

    Returns example course codes for common Ontario pathways that would satisfy
    unfulfilled compulsory requirements.

    Args:
        plan_courses: list of PlanCourse ORM objects.

    Returns:
        List of suggested course codes (strings).
    """
    # Determine which categories are already covered
    covered: dict[str, float] = {k: 0.0 for k in OSSD_COMPULSORY}

    active_courses = [pc for pc in plan_courses if pc.status != "dropped"]
    for pc in active_courses:
        cat = _resolve_compulsory_category(pc.course_code, getattr(pc, "subject_area", None), getattr(pc, "compulsory_category", None))
        if cat and cat in covered:
            req = OSSD_COMPULSORY[cat]
            if _grade_satisfies(pc.grade_level, req):
                covered[cat] += pc.credit_value

    # Map each unfulfilled category to a representative course code
    _SUGGESTION_MAP: dict[str, list[str]] = {
        "English": ["ENG1D", "ENG2D", "ENG3U", "ENG4U"],
        "Math": ["MPM1D", "MPM2D", "MCR3U"],
        "Science": ["SNC1D", "SNC2D"],
        "Canadian History": ["CHC2D"],
        "Canadian Geography": ["CGC1D"],
        "Arts": ["AVI1O"],
        "Health & PE": ["PPL1O"],
        "Civics": ["CHV2O"],
        "Career Studies": ["GLC2O"],
        "French": ["FSF1D"],
    }

    suggestions: list[str] = []
    existing_codes = {pc.course_code.upper() for pc in active_courses}

    for category, req in OSSD_COMPULSORY.items():
        shortfall = req["required"] - covered[category]
        if shortfall <= 0:
            continue
        for code in _SUGGESTION_MAP.get(category, []):
            if code not in existing_codes:
                suggestions.append(code)

    return suggestions
