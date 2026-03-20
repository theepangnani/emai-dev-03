"""Document Type Auto-Detection Service (§6.105.3, #1975).

Uses AI to classify uploaded documents into predefined types.
"""

import json
import logging

logger = logging.getLogger(__name__)

VALID_DOCUMENT_TYPES = [
    "teacher_notes",
    "past_exam",
    "project_brief",
    "lab_experiment",
    "course_syllabus",
    "reading_material",
    "lecture_slides",
    "custom",
]


def get_anthropic_client():
    """Get an OpenAI client for classification. Placeholder for DI."""
    from openai import OpenAI
    return OpenAI()


class DocumentClassifierService:
    """Classifies documents into predefined types using AI."""

    @staticmethod
    def classify(text: str, filename: str) -> dict:
        """Classify a document based on its text content.

        Returns dict with document_type and confidence.
        Fails open: returns custom with 0 confidence on any error.
        """
        if not text or not text.strip():
            return {"document_type": "custom", "confidence": 0.0}

        try:
            client = get_anthropic_client()
            response = client.messages.create(
                model="gpt-4o-mini",
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Classify this document (filename: {filename}) into one of these types: "
                            f"{', '.join(VALID_DOCUMENT_TYPES)}.\n\n"
                            f"Text (first 2000 chars):\n{text[:2000]}\n\n"
                            "Respond with JSON: {\"document_type\": \"...\", \"confidence\": 0.0-1.0}"
                        ),
                    }
                ],
            )

            raw = response.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3].strip()

            result = json.loads(raw)
            doc_type = result.get("document_type", "custom")
            confidence = float(result.get("confidence", 0.0))

            if doc_type not in VALID_DOCUMENT_TYPES:
                return {"document_type": "custom", "confidence": 0.0}

            return {"document_type": doc_type, "confidence": confidence}

        except Exception:
            logger.exception("Document classification failed")
            return {"document_type": "custom", "confidence": 0.0}
