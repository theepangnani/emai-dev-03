"""Tests for Study Guide Strategy Pattern Service (§6.105.2, #1974)."""
import pytest
from app.services.study_guide_strategy import (
    StudyGuideStrategyService,
    PROMPT_TEMPLATES,
    GOAL_MODIFIERS,
    DEFAULT_TEMPLATE,
    DOCUMENT_TYPES,
    STUDY_GOALS,
    TEMPLATE_PROMPTS,
    resolve_template_key,
)


class TestPromptTemplateMap:
    """Test the prompt template map has correct entries."""

    def test_all_document_types_have_templates(self):
        """Every document type except custom should have a template."""
        for doc_type in DOCUMENT_TYPES:
            if doc_type != "custom":
                assert doc_type in PROMPT_TEMPLATES, f"Missing template for {doc_type}"

    def test_all_study_goals_have_modifiers(self):
        """Every study goal should have a modifier."""
        for goal in STUDY_GOALS:
            assert goal in GOAL_MODIFIERS, f"Missing modifier for {goal}"


class TestStudyGuideStrategyService:
    """Test the strategy service prompt generation."""

    def test_default_template_when_no_type(self):
        """Should return concise default template when document_type is None."""
        result = StudyGuideStrategyService.get_prompt_template()
        assert "3-5 sentence summary" in result
        assert "sub-guides" in result

    def test_teacher_notes_template(self):
        """Teacher notes should produce concise summary."""
        result = StudyGuideStrategyService.get_prompt_template(document_type="teacher_notes")
        assert "3-5 sentence summary" in result
        assert "teacher notes" in result

    def test_past_exam_template(self):
        """Past exam should produce concise summary."""
        result = StudyGuideStrategyService.get_prompt_template(document_type="past_exam")
        assert "3-5 sentence summary" in result
        assert "past exam" in result

    def test_project_brief_template(self):
        """Project brief should produce concise summary."""
        result = StudyGuideStrategyService.get_prompt_template(document_type="project_brief")
        assert "3-5 sentence summary" in result
        assert "project" in result.lower()

    def test_lab_experiment_template(self):
        """Lab experiment should produce concise summary."""
        result = StudyGuideStrategyService.get_prompt_template(document_type="lab_experiment")
        assert "3-5 sentence summary" in result
        assert "experiment" in result.lower()

    def test_study_goal_modifier_appended(self):
        """Study goal modifier should be appended to template."""
        result = StudyGuideStrategyService.get_prompt_template(
            document_type="teacher_notes",
            study_goal="upcoming_test",
        )
        assert "teacher notes" in result  # From template
        assert "STUDY GOAL" in result  # From modifier

    def test_focus_area_appended(self):
        """Focus area should be appended to template."""
        result = StudyGuideStrategyService.get_prompt_template(
            document_type="teacher_notes",
            focus_area="quadratic equations only",
        )
        assert "quadratic equations only" in result
        assert "FOCUS AREA" in result

    def test_all_three_combined(self):
        """Document type + study goal + focus area should all be present."""
        result = StudyGuideStrategyService.get_prompt_template(
            document_type="course_syllabus",
            study_goal="final_exam",
            focus_area="Chapter 4-6",
        )
        assert "syllabus" in result.lower()  # Syllabus template
        assert "Final Exam" in result  # Goal modifier
        assert "Chapter 4-6" in result  # Focus area

    def test_invalid_document_type_falls_back(self):
        """Invalid document type should fall back to default template."""
        result = StudyGuideStrategyService.get_prompt_template(document_type="invalid_type")
        assert "3-5 sentence summary" in result  # Default template

    def test_custom_type_uses_default(self):
        """Custom document type should use default template."""
        result = StudyGuideStrategyService.get_prompt_template(document_type="custom")
        assert "3-5 sentence summary" in result

    def test_system_prompt_varies_by_type(self):
        """System prompt should contain type-specific context."""
        notes_prompt = StudyGuideStrategyService.get_system_prompt("teacher_notes")
        exam_prompt = StudyGuideStrategyService.get_system_prompt("past_exam")
        assert "notes" in notes_prompt.lower()
        assert "exam" in exam_prompt.lower()
        assert notes_prompt != exam_prompt

    def test_system_prompt_default(self):
        """Default system prompt should be generic."""
        result = StudyGuideStrategyService.get_system_prompt(None)
        assert "ClassBridge" in result

    def test_different_types_produce_different_templates(self):
        """Each document type should produce a meaningfully different template."""
        templates = {}
        for doc_type in DOCUMENT_TYPES:
            if doc_type == "custom":
                continue
            templates[doc_type] = StudyGuideStrategyService.get_prompt_template(document_type=doc_type)

        # All should be unique
        unique_templates = set(templates.values())
        assert len(unique_templates) == len(templates), "Some document types produce identical templates"


# ── UTDF Template Resolver Tests (S15 #2961) ────────────────────────

class TestResolveTemplateKey:
    """Test the resolve_template_key function."""

    def test_resolve_template_math_worksheet(self):
        """Math + worksheet should resolve to 'worksheet_math_word_problems'."""
        key = resolve_template_key("teacher_notes", "math", "worksheet")
        assert key == "worksheet_math_word_problems"
        assert key in TEMPLATE_PROMPTS

    def test_resolve_template_generic(self):
        """Unknown subject + study_guide should resolve to 'study_guide_overview'."""
        key = resolve_template_key("teacher_notes", "unknown", "study_guide")
        assert key == "study_guide_overview"
        assert key in TEMPLATE_PROMPTS

    def test_resolve_template_high_level_summary(self):
        """Any input with requested_output='high_level_summary' should return 'high_level_summary'."""
        key = resolve_template_key("past_exam", "math", "high_level_summary")
        assert key == "high_level_summary"
        assert key in TEMPLATE_PROMPTS

    def test_resolve_template_math_study_guide(self):
        """Math + study_guide should resolve to 'study_guide_math'."""
        key = resolve_template_key("textbook_excerpt", "math", "study_guide")
        assert key == "study_guide_math"

    def test_resolve_template_science_study_guide(self):
        """Science + study_guide should resolve to 'study_guide_science'."""
        key = resolve_template_key("teacher_notes", "science", "study_guide")
        assert key == "study_guide_science"

    def test_resolve_template_english_study_guide(self):
        """English + study_guide should resolve to 'study_guide_english'."""
        key = resolve_template_key("textbook_excerpt", "english", "study_guide")
        assert key == "study_guide_english"

    def test_resolve_template_french_study_guide(self):
        """French + study_guide should resolve to 'study_guide_english' (shared template)."""
        key = resolve_template_key("teacher_notes", "french", "study_guide")
        assert key == "study_guide_english"

    def test_resolve_template_english_worksheet(self):
        """English + worksheet should resolve to 'worksheet_english'."""
        key = resolve_template_key("teacher_notes", "english", "worksheet")
        assert key == "worksheet_english"

    def test_resolve_template_french_worksheet(self):
        """French + worksheet should resolve to 'worksheet_french'."""
        key = resolve_template_key("teacher_notes", "french", "worksheet")
        assert key == "worksheet_french"

    def test_resolve_template_generic_worksheet(self):
        """Unknown subject + worksheet should resolve to 'worksheet_general'."""
        key = resolve_template_key("teacher_notes", "unknown", "worksheet")
        assert key == "worksheet_general"

    def test_all_template_keys_exist_in_prompts(self):
        """Every possible key from resolve_template_key should exist in TEMPLATE_PROMPTS."""
        subjects = ["math", "science", "english", "french", "unknown"]
        outputs = ["study_guide", "worksheet", "high_level_summary"]
        for subj in subjects:
            for out in outputs:
                key = resolve_template_key("teacher_notes", subj, out)
                assert key in TEMPLATE_PROMPTS, f"Key '{key}' not in TEMPLATE_PROMPTS"


class TestGoalModifierWithTemplateKey:
    """Test that GOAL_MODIFIERS are still applied when template_key is used."""

    def test_goal_modifier_layered(self):
        """Goal modifier should be appended even when using a template_key."""
        result = StudyGuideStrategyService.get_prompt_template(
            template_key="study_guide_math",
            study_goal="upcoming_test",
        )
        # Should contain the math template content
        assert "formulas" in result.lower() or "math" in result.lower()
        # Should also contain the goal modifier
        assert "STUDY GOAL" in result
        assert "Upcoming Test" in result

    def test_template_key_takes_priority_over_document_type(self):
        """template_key should override document_type for template selection."""
        result = StudyGuideStrategyService.get_prompt_template(
            document_type="past_exam",
            template_key="worksheet_math_word_problems",
        )
        # Should use the worksheet template, not the past_exam template
        assert "word problem" in result.lower()

    def test_template_key_with_focus_area(self):
        """template_key + focus_area should both be present."""
        result = StudyGuideStrategyService.get_prompt_template(
            template_key="study_guide_science",
            focus_area="photosynthesis",
        )
        assert "FOCUS AREA" in result
        assert "photosynthesis" in result
