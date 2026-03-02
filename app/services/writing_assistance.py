"""Writing Assistance Service — AI-powered essay analysis and improvement.

Uses Anthropic Claude (via ai_service.generate_content) to:
  - Analyze student writing for grammar, clarity, structure, argumentation, vocabulary
  - Produce an overall score (0-100)
  - Generate an improved version of the text
  - Apply specific improvement instructions (make formal, add evidence, etc.)
"""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.writing_assistance import WritingAssistanceSession, WritingTemplate
from app.schemas.writing_assistance import (
    WritingAnalysisResponse,
    WritingFeedbackItem,
    WritingImproveResponse,
    WritingSessionDetail,
    WritingSessionSummary,
    WritingTemplateResponse,
)
from app.services.ai_service import generate_content

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Default writing templates seeded at startup
# ---------------------------------------------------------------------------

_DEFAULT_TEMPLATES = [
    {
        "name": "5-Paragraph Essay",
        "description": "Classic essay structure with introduction, three body paragraphs, and conclusion.",
        "template_type": "essay",
        "structure_outline": """# 5-Paragraph Essay Structure

## Introduction
- **Hook:** Start with an interesting fact, question, or anecdote to grab the reader's attention.
- **Background:** Provide 2-3 sentences of context about your topic.
- **Thesis Statement:** State your main argument clearly in one or two sentences.

## Body Paragraph 1 — First Main Point
- **Topic Sentence:** State the first main supporting point.
- **Evidence:** Provide a quote, statistic, or example.
- **Analysis:** Explain how the evidence supports your thesis.
- **Transition:** Link to the next paragraph.

## Body Paragraph 2 — Second Main Point
- **Topic Sentence:** State the second main supporting point.
- **Evidence:** Provide a quote, statistic, or example.
- **Analysis:** Explain how the evidence supports your thesis.
- **Transition:** Link to the next paragraph.

## Body Paragraph 3 — Third Main Point
- **Topic Sentence:** State the third main supporting point.
- **Evidence:** Provide a quote, statistic, or example.
- **Analysis:** Explain how the evidence supports your thesis.
- **Transition:** Lead into the conclusion.

## Conclusion
- **Restate Thesis:** Paraphrase your thesis (don't copy it word for word).
- **Summarize:** Briefly recap your three main points.
- **Closing Statement:** End with a thought-provoking statement or call to action.
""",
    },
    {
        "name": "Scientific Report",
        "description": "Standard scientific report format for lab work and research summaries.",
        "template_type": "report",
        "structure_outline": """# Scientific Report Structure

## Title
A clear, concise title describing the experiment or study.

## Abstract (100-200 words)
A brief summary of the purpose, methods, key results, and conclusion.

## Introduction
- **Background:** Relevant theory and prior research.
- **Purpose/Hypothesis:** What you are testing and your prediction.

## Materials and Methods
- List of all equipment and materials used.
- Step-by-step procedure in past tense, written clearly enough to replicate.

## Results
- Present data using tables and/or graphs.
- Describe observations without interpreting them.
- Include units for all measurements.

## Discussion
- **Analysis:** Interpret your results. Do they support your hypothesis?
- **Sources of Error:** Identify potential errors and their impact.
- **Comparison:** How do your results compare to accepted values or prior research?
- **Improvements:** What would you do differently?

## Conclusion
A concise summary of what was discovered and whether the hypothesis was supported.

## References
List all sources in APA or MLA format.
""",
    },
    {
        "name": "Formal Letter",
        "description": "Standard business/formal letter format for professional communication.",
        "template_type": "letter",
        "structure_outline": """# Formal Letter Structure

## Sender's Address
Your name and address (top right or left, depending on style).

## Date
Full date (e.g., March 2, 2026).

## Recipient's Address
Name, title, organization, and address of the person you are writing to.

## Salutation
- If you know the name: *Dear Mr./Ms./Dr. [Last Name],*
- If you do not know the name: *Dear Sir or Madam,*

## Opening Paragraph
State the purpose of the letter clearly and directly in the first sentence.

## Body Paragraph(s)
- Provide all relevant details, evidence, or arguments.
- Keep each paragraph focused on one main idea.
- Use formal, professional language throughout.

## Closing Paragraph
- Summarize your main point or request.
- State what action you expect or are requesting.
- Thank the reader for their time.

## Complimentary Close
- Formal: *Yours faithfully,* (when you do not know the name)
- Semi-formal: *Yours sincerely,* (when you know the name)

## Signature
Your handwritten signature (if printed), then your full name typed below.
""",
    },
    {
        "name": "Lab Report",
        "description": "Detailed lab report template for Ontario science courses.",
        "template_type": "lab",
        "structure_outline": """# Lab Report Structure

## Title Page
- Title of the experiment
- Your name, partner names, course, and date

## Purpose
A one or two sentence statement of what you were trying to find out or demonstrate.

## Hypothesis
Your prediction before the experiment, written as an *if–then* statement.
> *If [independent variable] is [changed in this way], then [dependent variable] will [predicted outcome] because [scientific reasoning].*

## Materials
Bulleted list of all materials, chemicals, and equipment with quantities.

## Procedure
Numbered, step-by-step instructions written in past tense. Include safety precautions.

## Observations / Data
- **Qualitative Observations:** What you saw, smelled, heard (use descriptive language).
- **Quantitative Data:** Measurements recorded in a properly labelled data table with units.

## Calculations
Show all formulas used, sample calculations, and final results with correct significant figures.

## Analysis Questions
Answer each analysis question provided by your teacher in full sentences.

## Discussion
- Were your results consistent with your hypothesis? Explain using data.
- What sources of error could have affected your results?
- How could the experiment be improved?

## Conclusion
A concise paragraph summarizing what you learned and whether your hypothesis was supported.
""",
    },
]


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def analyze_writing(
    user_id: int,
    text: str,
    title: str,
    db: Session,
    course_id: Optional[int] = None,
    assignment_type: str = "essay",
) -> WritingAnalysisResponse:
    """Analyze student writing and return scored feedback with an improved version.

    Steps:
    1. Count words.
    2. Send to Claude for analysis (grammar, clarity, structure, argumentation, vocabulary).
    3. Parse JSON response.
    4. Store WritingAssistanceSession in DB.
    5. Return structured response.
    """
    word_count = len(text.split())

    system_prompt = (
        "You are an expert academic writing coach for K-12 and post-secondary students. "
        "You provide constructive, encouraging feedback that helps students improve their writing skills. "
        "Always return valid JSON — never include markdown code fences in your output."
    )

    user_prompt = f"""Analyze the following student {assignment_type} and provide detailed feedback.

Assignment type: {assignment_type}
Title: {title}

Student text:
{text}

Return a JSON object with exactly this structure:
{{
  "overall_score": <integer 0-100>,
  "feedback": [
    {{
      "type": "<grammar|clarity|structure|argumentation|vocabulary>",
      "message": "<specific issue found>",
      "suggestion": "<actionable improvement suggestion>",
      "severity": "<info|warning|error>"
    }}
  ],
  "improved_text": "<full improved version of the student text>",
  "summary": "<2-3 sentence overall assessment>"
}}

Scoring guide:
- 90-100: Excellent — publication ready
- 75-89: Good — minor improvements needed
- 60-74: Satisfactory — several areas to improve
- 45-59: Needs work — significant revision required
- 0-44: Major revision needed

Provide at least 3 and at most 10 feedback items. Each feedback item must be specific and actionable.
The improved_text should be a polished version that preserves the student's ideas and voice.
Return ONLY valid JSON, no other text."""

    # Call AI with retry on JSON parse error
    raw_response = await generate_content(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=4000,
        temperature=0.4,
    )

    parsed = _parse_ai_response(raw_response)

    if parsed is None:
        # Retry once with explicit JSON reminder
        retry_prompt = user_prompt + "\n\nIMPORTANT: Your previous response was not valid JSON. Return ONLY the JSON object, no markdown, no explanation."
        raw_response = await generate_content(
            prompt=retry_prompt,
            system_prompt=system_prompt,
            max_tokens=4000,
            temperature=0.2,
        )
        parsed = _parse_ai_response(raw_response)

    if parsed is None:
        # Fallback: return a minimal response so the UI doesn't break
        logger.error("Writing analysis AI returned unparseable JSON for user_id=%d", user_id)
        parsed = {
            "overall_score": 50,
            "feedback": [
                {
                    "type": "overall",
                    "message": "Unable to fully analyze this text at this time.",
                    "suggestion": "Please try again or check your text for any unusual characters.",
                    "severity": "info",
                }
            ],
            "improved_text": text,
            "summary": "Analysis could not be completed.",
        }

    overall_score = int(parsed.get("overall_score", 50))
    raw_feedback = parsed.get("feedback", [])
    improved_text = parsed.get("improved_text", text)

    # Validate and coerce feedback items
    feedback_items = []
    for item in raw_feedback:
        try:
            feedback_items.append(
                WritingFeedbackItem(
                    type=item.get("type", "overall"),
                    message=item.get("message", ""),
                    suggestion=item.get("suggestion", ""),
                    severity=item.get("severity", "info"),
                )
            )
        except Exception:
            pass  # Skip malformed items

    # Serialize feedback to JSON-compatible list for storage
    feedback_json = [f.model_dump() for f in feedback_items]

    # Store session in DB
    session = WritingAssistanceSession(
        user_id=user_id,
        course_id=course_id,
        title=title,
        assignment_type=assignment_type,
        original_text=text,
        improved_text=improved_text,
        feedback=feedback_json,
        overall_score=overall_score,
        word_count=word_count,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(
        "Writing analysis complete | user_id=%d | session_id=%d | score=%d | feedback_count=%d",
        user_id,
        session.id,
        overall_score,
        len(feedback_items),
    )

    return WritingAnalysisResponse(
        session_id=session.id,
        overall_score=overall_score,
        feedback=feedback_items,
        improved_text=improved_text,
        suggestions_count=len(feedback_items),
        word_count=word_count,
    )


async def improve_writing(
    session_id: int,
    user_id: int,
    instruction: str,
    db: Session,
) -> WritingImproveResponse:
    """Apply a specific improvement instruction to the session's original text.

    Does NOT save the result — lets the user review and choose to apply it.
    """
    session = (
        db.query(WritingAssistanceSession)
        .filter(
            WritingAssistanceSession.id == session_id,
            WritingAssistanceSession.user_id == user_id,
        )
        .first()
    )

    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Writing session not found")

    system_prompt = (
        "You are an expert academic writing editor. "
        "Apply the user's instruction to improve the text while preserving their ideas and voice. "
        "Return only the improved text, no commentary or explanation."
    )

    user_prompt = f"""Apply the following instruction to improve this text.

Instruction: {instruction}

Original text:
{session.original_text}

Return only the improved version of the text."""

    improved_text = await generate_content(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=3000,
        temperature=0.5,
    )

    logger.info(
        "Writing improvement applied | session_id=%d | user_id=%d | instruction=%s",
        session_id,
        user_id,
        instruction[:80],
    )

    return WritingImproveResponse(
        improved_text=improved_text.strip(),
        instruction=instruction,
    )


def get_sessions(user_id: int, db: Session) -> list[WritingSessionSummary]:
    """Return all writing sessions for a user (summary only, no full text)."""
    sessions = (
        db.query(WritingAssistanceSession)
        .filter(WritingAssistanceSession.user_id == user_id)
        .order_by(WritingAssistanceSession.created_at.desc())
        .all()
    )

    results = []
    for s in sessions:
        count = len(s.feedback) if s.feedback else 0
        results.append(
            WritingSessionSummary(
                id=s.id,
                title=s.title,
                assignment_type=s.assignment_type,
                overall_score=s.overall_score,
                word_count=s.word_count,
                suggestions_count=count,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return results


def get_session(session_id: int, user_id: int, db: Session) -> WritingSessionDetail:
    """Return the full writing session including text and feedback."""
    from fastapi import HTTPException

    session = (
        db.query(WritingAssistanceSession)
        .filter(
            WritingAssistanceSession.id == session_id,
            WritingAssistanceSession.user_id == user_id,
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="Writing session not found")

    # Coerce stored feedback JSON back into WritingFeedbackItem list
    feedback_items = None
    if session.feedback:
        feedback_items = []
        for item in session.feedback:
            try:
                feedback_items.append(WritingFeedbackItem(**item))
            except Exception:
                pass

    return WritingSessionDetail(
        id=session.id,
        title=session.title,
        assignment_type=session.assignment_type,
        original_text=session.original_text,
        improved_text=session.improved_text,
        feedback=feedback_items,
        overall_score=session.overall_score,
        word_count=session.word_count,
        course_id=session.course_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def get_templates(db: Session) -> list[WritingTemplateResponse]:
    """Return all active writing templates."""
    templates = (
        db.query(WritingTemplate)
        .filter(WritingTemplate.is_active.is_(True))
        .order_by(WritingTemplate.id)
        .all()
    )
    return [WritingTemplateResponse.model_validate(t) for t in templates]


def seed_templates(db: Session) -> None:
    """Create default writing templates if they do not already exist (idempotent)."""
    existing_names = {
        t.name for t in db.query(WritingTemplate.name).all()
    }

    added = 0
    for tmpl in _DEFAULT_TEMPLATES:
        if tmpl["name"] not in existing_names:
            db.add(WritingTemplate(**tmpl))
            added += 1

    if added:
        db.commit()
        logger.info("Seeded %d writing templates", added)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_ai_response(raw: str) -> Optional[dict]:
    """Try to parse the AI response as JSON, stripping markdown fences if present."""
    text = raw.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        inner = "\n".join(lines[1:-1]) if len(lines) > 2 else ""
        text = inner.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first { and last } and parse between them
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None
