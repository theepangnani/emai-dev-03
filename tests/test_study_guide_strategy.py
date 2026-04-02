"""Tests for Study Guide Strategy Pattern Service (§6.105.2, #1974)."""
import pytest
from app.services.study_guide_strategy import (
    StudyGuideStrategyService,
    PROMPT_TEMPLATES,
    GOAL_MODIFIERS,
    DEFAULT_TEMPLATE,
    DOCUMENT_TYPES,
    STUDY_GOALS,
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
