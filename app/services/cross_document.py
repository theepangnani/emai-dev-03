"""Cross-Document Intelligence Service (§6.105.6, #1978).

Finds relationships between uploaded documents and generates insights.
"""

import re
from collections import Counter

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "this", "that", "these",
    "those", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "can", "shall", "not", "no", "if", "then", "than", "so",
    "as", "up", "out", "into", "about", "he", "she", "we", "they",
    "me", "him", "her", "us", "them", "my", "his", "its", "our",
    "your", "their", "go", "are", "am",
}


class CrossDocumentService:
    """Finds relationships between documents and generates insights."""

    @staticmethod
    def _extract_keywords(text: str) -> dict[str, int]:
        """Extract meaningful keywords from text with frequency counts.

        Filters stop words and words shorter than 3 characters.
        """
        if not text:
            return {}

        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        filtered = [w for w in words if w not in STOP_WORDS]
        return dict(Counter(filtered))

    @staticmethod
    def _generate_insight(
        new_title: str,
        related_title: str,
        shared_topics: list[str],
        new_doc_type: str | None,
        related_doc_type: str | None,
        same_course: bool,
    ) -> str:
        """Generate a human-readable insight about the relationship."""
        topics_str = ", ".join(shared_topics[:3])

        if same_course:
            context = "same course"
        else:
            context = "Cross-course connection"

        # Specific combos
        if {new_doc_type, related_doc_type} & {"past_exam"} and {
            new_doc_type,
            related_doc_type,
        } & {"teacher_notes"}:
            return (
                f"Your exam and notes both cover {topics_str}. "
                f"Review your notes on these topics to prepare."
            )

        return (
            f"Found {context} link between \"{new_title}\" and \"{related_title}\" "
            f"on shared topics: {topics_str}."
        )
