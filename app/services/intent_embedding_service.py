"""
Embedding-based intent classification fallback.

Pre-computes anchor phrase embeddings at startup. At runtime, embeds the user
message and picks the intent with the highest cosine similarity.
"""
from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Anchor phrases per intent — add more to improve coverage
INTENT_ANCHORS: dict[str, list[str]] = {
    "search": [
        "find my course",
        "show me my assignments",
        "search for a task",
        "list my study guides",
        "where is my quiz",
        "my notes",
        "what tasks do I have",
        "show me my materials",
        "look up",
        "find Noah",
        "Thanushan",
        "biology",
        "math homework",
        "my flashcards",
    ],
    "help": [
        "how do I add a child",
        "why can't I upload a file",
        "explain study guides",
        "what is a flashcard",
        "how does messaging work",
        "how to create a course",
        "what does this button do",
        "I need help with",
        "tutorial",
        "getting started",
        "how do I use",
        "can you explain",
    ],
    "action": [
        "create a new task",
        "upload a file",
        "generate a quiz",
        "add a course",
        "make a new assignment",
        "start a study guide",
        "new course",
        "add material",
    ],
}

CONFIDENCE_THRESHOLD = 0.60  # min cosine similarity to trust embedding result


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


@dataclass
class IntentEmbeddingService:
    _anchor_embeddings: dict[str, list[list[float]]] = field(default_factory=dict)
    _ready: bool = False

    def initialize(self, openai_api_key: str) -> None:
        """Pre-compute anchor embeddings at startup. Call once from main.py or lifespan."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)

            all_phrases: list[str] = []
            intent_map: list[str] = []
            for intent, phrases in INTENT_ANCHORS.items():
                for phrase in phrases:
                    all_phrases.append(phrase)
                    intent_map.append(intent)

            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=all_phrases,
            )
            embeddings = [item.embedding for item in response.data]

            self._anchor_embeddings = {intent: [] for intent in INTENT_ANCHORS}
            for intent, embedding in zip(intent_map, embeddings):
                self._anchor_embeddings[intent].append(embedding)

            self._ready = True
            logger.info("IntentEmbeddingService: anchor embeddings loaded (%d phrases)", len(all_phrases))
        except Exception as e:
            logger.warning("IntentEmbeddingService: failed to initialize — %s", e)
            self._ready = False

    def classify(self, message: str, openai_api_key: str) -> str | None:
        """
        Embed message and return the best-matching intent, or None if below threshold.
        Returns 'search' | 'action' | 'help' | None
        """
        if not self._ready:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=[message],
            )
            msg_embedding = response.data[0].embedding

            best_intent = None
            best_score = -1.0
            for intent, anchors in self._anchor_embeddings.items():
                # Average similarity across all anchor phrases for this intent
                scores = [_cosine_similarity(msg_embedding, anchor) for anchor in anchors]
                avg_score = sum(scores) / len(scores) if scores else 0.0
                if avg_score > best_score:
                    best_score = avg_score
                    best_intent = intent

            if best_score >= CONFIDENCE_THRESHOLD:
                logger.debug("IntentEmbeddingService: '%s' → %s (score=%.3f)", message[:50], best_intent, best_score)
                return best_intent
            else:
                logger.debug("IntentEmbeddingService: '%s' → below threshold (score=%.3f)", message[:50], best_score)
                return None
        except Exception as e:
            logger.warning("IntentEmbeddingService: classify failed — %s", e)
            return None


# Singleton
intent_embedding_service = IntentEmbeddingService()
