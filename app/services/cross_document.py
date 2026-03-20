"""
Cross-Document Intelligence Service (§6.105.6, #1978)

Detects relationships between a student's uploaded documents over time.
Priority 2 differentiator — requires persistent upload history per student,
not achievable in a one-off AI chat session.

Example insight:
"You uploaded Chapter 5 notes last week and this practice test today.
The test covers 3 topics you have not yet reviewed."
"""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.course_content import CourseContent

logger = get_logger(__name__)

# Common stop words to exclude from keyword extraction
STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "this", "that", "these",
    "those", "it", "its", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "they", "them", "their", "what",
    "which", "who", "whom", "page", "student", "name", "date", "class",
})


class CrossDocumentService:
    """Service for detecting relationships between uploaded documents."""

    def __init__(self, db: Session):
        self.db = db

    def find_relationships(
        self,
        user_id: int,
        new_content_id: int,
        days_back: int = 30,
        max_related: int = 5,
    ) -> list[dict]:
        """
        Find related documents for a student based on topic overlap.

        Args:
            user_id: The student's user ID
            new_content_id: The newly uploaded CourseContent ID
            days_back: How far back to look (default 30 days)
            max_related: Maximum number of related documents to return

        Returns:
            List of dicts with keys: content_id, title, overlap_score,
            shared_topics, relationship_type, insight
        """
        # Get the new document
        new_content = self.db.query(CourseContent).filter(
            CourseContent.id == new_content_id
        ).first()

        if not new_content or not new_content.text_content:
            return []

        # Extract keywords from new document
        new_keywords = self._extract_keywords(new_content.text_content)
        if not new_keywords:
            return []

        # Find recent documents by this user (or in same courses)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        recent_contents = (
            self.db.query(CourseContent)
            .filter(
                CourseContent.id != new_content_id,
                CourseContent.created_by_user_id == user_id,
                CourseContent.created_at >= cutoff,
                CourseContent.text_content.isnot(None),
                CourseContent.archived_at.is_(None),
            )
            .order_by(CourseContent.created_at.desc())
            .limit(20)  # Cap to avoid expensive comparisons
            .all()
        )

        if not recent_contents:
            return []

        relationships = []
        new_keyword_set = set(new_keywords.keys())

        for content in recent_contents:
            if not content.text_content:
                continue

            other_keywords = self._extract_keywords(content.text_content)
            if not other_keywords:
                continue

            other_keyword_set = set(other_keywords.keys())
            shared = new_keyword_set & other_keyword_set

            if len(shared) < 3:  # Minimum overlap threshold
                continue

            # Calculate overlap score (Jaccard similarity)
            union = new_keyword_set | other_keyword_set
            overlap_score = len(shared) / len(union) if union else 0

            # Get top shared topics (by combined frequency)
            shared_topics = sorted(
                shared,
                key=lambda k: new_keywords.get(k, 0) + other_keywords.get(k, 0),
                reverse=True,
            )[:5]

            # Determine relationship type
            same_course = content.course_id == new_content.course_id
            rel_type = "same_course" if same_course else "cross_course"

            # Generate insight
            insight = self._generate_insight(
                new_title=new_content.title,
                related_title=content.title,
                shared_topics=shared_topics,
                new_doc_type=getattr(new_content, 'document_type', None),
                related_doc_type=getattr(content, 'document_type', None),
                same_course=same_course,
            )

            relationships.append({
                "content_id": content.id,
                "title": content.title,
                "overlap_score": round(overlap_score, 3),
                "shared_topics": shared_topics,
                "relationship_type": rel_type,
                "insight": insight,
                "created_at": content.created_at.isoformat() if content.created_at else None,
            })

        # Sort by overlap score and return top results
        relationships.sort(key=lambda r: r["overlap_score"], reverse=True)
        result = relationships[:max_related]

        if result:
            logger.info(
                f"Found {len(result)} related documents for content_id={new_content_id}, "
                f"user_id={user_id} (top overlap: {result[0]['overlap_score']})"
            )

        return result

    def get_context_enrichment(
        self,
        user_id: int,
        new_content_id: int,
    ) -> str | None:
        """
        Generate a context enrichment string for the AI prompt based on
        cross-document relationships.

        Returns:
            A string to append to the AI prompt, or None if no relationships found
        """
        relationships = self.find_relationships(user_id, new_content_id, max_related=3)
        if not relationships:
            return None

        lines = ["\n**CROSS-DOCUMENT CONTEXT (from the student's recent uploads):**"]
        for rel in relationships:
            lines.append(f"- Related to \"{rel['title']}\" (shared topics: {', '.join(rel['shared_topics'][:3])})")
            if rel["insight"]:
                lines.append(f"  → {rel['insight']}")

        return "\n".join(lines)

    @staticmethod
    def _extract_keywords(text: str, top_n: int = 50) -> dict[str, int]:
        """Extract top keywords from text using simple frequency analysis."""
        # Tokenize: extract words 3+ chars, lowercase
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

        # Filter stop words
        filtered = [w for w in words if w not in STOP_WORDS]

        # Count frequencies
        counts = Counter(filtered)

        # Return top N
        return dict(counts.most_common(top_n))

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

        # Special case: notes + exam combination
        notes_types = {"teacher_notes", "textbook_excerpt"}
        exam_types = {"past_exam", "mock_exam"}

        if new_doc_type in exam_types and related_doc_type in notes_types:
            return f"This exam covers topics from your earlier notes \"{related_title}\". Shared topics: {topics_str}."

        if new_doc_type in notes_types and related_doc_type in exam_types:
            return f"These notes relate to a previous exam \"{related_title}\". Review those exam questions for practice. Shared topics: {topics_str}."

        if same_course:
            return f"This material shares topics with \"{related_title}\" from the same course: {topics_str}."

        return f"Cross-course connection with \"{related_title}\": {topics_str}."
