"""
Document Type Auto-Detection Service (#1975)

Classifies uploaded documents into one of 8 document types using a lightweight
AI inference call. Returns the best-match type with confidence score.
"""
import json
from app.core.logging_config import get_logger
from app.services.ai_service import get_anthropic_client

logger = get_logger(__name__)

VALID_DOCUMENT_TYPES = [
    "teacher_notes",
    "course_syllabus",
    "past_exam",
    "mock_exam",
    "project_brief",
    "lab_experiment",
    "textbook_excerpt",
    "custom",
    "worksheet",
    "student_test",
    "quiz_paper",
]

CLASSIFICATION_PROMPT = """You are a document classifier for a K-12 education platform. Analyze the following document content and filename to determine the document type.

Document types:
- teacher_notes: Lecture slides, class notes, printed handouts, annotated worksheets
- course_syllabus: Unit overview, course outline, curriculum map, topic schedule
- past_exam: Prior year exam, returned test with marks, completed quiz
- mock_exam: Sample questions, review sheet, prep quiz, unseen practice paper
- project_brief: Assignment rubric, project guidelines, inquiry task, performance task
- lab_experiment: Lab procedure, experiment report template, data collection sheet
- textbook_excerpt: Chapter section, reference reading, supplementary material
- custom: Cannot be classified into any of the above categories

Respond with ONLY a JSON object (no markdown fences):
{"document_type": "<type>", "confidence": <0.0-1.0>}"""


class DocumentClassifierService:
    """Service for auto-detecting document type from uploaded content."""

    @staticmethod
    def classify(extracted_text: str, filename: str = "") -> dict:
        """
        Classify a document based on its extracted text and filename.

        Args:
            extracted_text: The extracted text content from the uploaded document
            filename: The original filename of the uploaded document

        Returns:
            dict with keys: document_type (str), confidence (float)
        """
        if not extracted_text or not extracted_text.strip():
            logger.info("Empty text provided for classification, returning 'custom'")
            return {"document_type": "custom", "confidence": 0.0}

        # Use first 800 chars for classification (cost-efficient)
        text_snippet = extracted_text[:800].strip()

        user_message = f"Filename: {filename}\n\nDocument content (excerpt):\n{text_snippet}"

        try:
            client = get_anthropic_client()
            result = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                system=CLASSIFICATION_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            response_text = result.content[0].text.strip()
            # Strip markdown fences if present
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            parsed = json.loads(response_text)
            doc_type = parsed.get("document_type", "custom")
            confidence = float(parsed.get("confidence", 0.0))

            # Validate document type
            if doc_type not in VALID_DOCUMENT_TYPES:
                logger.warning(f"AI returned invalid document_type: {doc_type}, falling back to 'custom'")
                doc_type = "custom"
                confidence = 0.0

            # Low confidence fallback
            if confidence < 0.4:
                logger.info(f"Low confidence ({confidence}) for type '{doc_type}', returning as-is for user confirmation")

            logger.info(f"Document classified as '{doc_type}' with confidence {confidence:.2f}")
            return {"document_type": doc_type, "confidence": confidence}

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification response: {e}")
            return {"document_type": "custom", "confidence": 0.0}
        except Exception as e:
            logger.warning(f"Document classification failed (returning custom): {e}")
            return {"document_type": "custom", "confidence": 0.0}
