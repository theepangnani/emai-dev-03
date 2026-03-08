"""
Help Embedding Service — RAG pipeline for the AI Help Chatbot.

Loads YAML knowledge-base files, chunks them, computes OpenAI embeddings,
and provides cosine-similarity search with optional role filtering.
Embeddings are cached to disk and invalidated when YAML content changes.
"""

import json
import hashlib
import logging
import yaml
import numpy as np
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "data" / "help_knowledge"
CACHE_FILE = KNOWLEDGE_BASE_DIR / ".embeddings_cache.json"


@dataclass
class ChunkResult:
    text: str
    source: str       # e.g., "faq", "features", "videos", "pages"
    source_id: str     # e.g., "faq-google-1"
    metadata: dict     # full original entry
    score: float       # cosine similarity score


class HelpEmbeddingService:
    def __init__(self):
        self.chunks: list[dict] = []  # {text, embedding, source, source_id, metadata}
        self._initialized = False

    # ------------------------------------------------------------------
    # YAML loading
    # ------------------------------------------------------------------

    def _load_yaml(self, filename: str) -> list[dict]:
        """Load a YAML file from the knowledge base directory."""
        filepath = KNOWLEDGE_BASE_DIR / filename
        if not filepath.exists():
            logger.warning(f"Knowledge base file not found: {filepath}")
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Chunking strategies (one chunk per logical entry)
    # ------------------------------------------------------------------

    def _chunk_faq(self, entries: list[dict]) -> list[dict]:
        """Each FAQ Q&A pair = 1 chunk."""
        chunks = []
        for entry in entries:
            text = f"Question: {entry.get('question', '')}\nAnswer: {entry.get('answer', '')}"
            roles = entry.get("roles", [])
            if roles:
                text += f"\nApplicable roles: {', '.join(roles)}"
            chunks.append({
                "text": text,
                "source": "faq",
                "source_id": entry.get("id", ""),
                "metadata": entry,
            })
        return chunks

    def _chunk_features(self, entries: list[dict]) -> list[dict]:
        """Each feature = 1 chunk."""
        chunks = []
        for entry in entries:
            how_to = entry.get("how_to", [])
            how_to_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(how_to))
            text = f"Feature: {entry.get('name', '')}\n{entry.get('description', '')}"
            if how_to_text:
                text += f"\nHow to use:\n{how_to_text}"
            roles = entry.get("roles", [])
            if roles:
                text += f"\nAvailable to: {', '.join(roles)}"
            chunks.append({
                "text": text,
                "source": "features",
                "source_id": entry.get("id", ""),
                "metadata": entry,
            })
        return chunks

    def _chunk_videos(self, entries: list[dict]) -> list[dict]:
        """Each video = 1 chunk."""
        chunks = []
        for entry in entries:
            text = f"Tutorial Video: {entry.get('title', '')}\n{entry.get('description', '')}"
            tags = entry.get("tags", [])
            if tags:
                text += f"\nTopics: {', '.join(tags)}"
            chunks.append({
                "text": text,
                "source": "videos",
                "source_id": entry.get("id", ""),
                "metadata": entry,
            })
        return chunks

    def _chunk_pages(self, entries: list[dict]) -> list[dict]:
        """Each page = 1 chunk."""
        chunks = []
        for entry in entries:
            actions = entry.get("key_actions", [])
            actions_text = ", ".join(actions)
            text = f"Page: {entry.get('page_name', '')} ({entry.get('route', '')})\n{entry.get('description', '')}"
            if actions_text:
                text += f"\nKey actions: {actions_text}"
            roles = entry.get("roles", [])
            if roles:
                text += f"\nAccessible to: {', '.join(roles)}"
            chunks.append({
                "text": text,
                "source": "pages",
                "source_id": entry.get("id", ""),
                "metadata": entry,
            })
        return chunks

    # ------------------------------------------------------------------
    # Embedding cache (JSON on disk, keyed by content hash)
    # ------------------------------------------------------------------

    def _compute_content_hash(self) -> str:
        """Hash all YAML files to detect changes."""
        hasher = hashlib.md5(usedforsecurity=False)
        for filename in sorted(["faq.yaml", "features.yaml", "videos.yaml", "pages.yaml"]):
            filepath = KNOWLEDGE_BASE_DIR / filename
            if filepath.exists():
                hasher.update(filepath.read_bytes())
        return hasher.hexdigest()

    def _load_cache(self, content_hash: str) -> Optional[list[list[float]]]:
        """Load cached embeddings if content hash matches."""
        if not CACHE_FILE.exists():
            return None
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
            if cache.get("content_hash") == content_hash:
                logger.info("Using cached embeddings")
                return cache.get("embeddings", [])
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_cache(self, content_hash: str, embeddings: list[list[float]]):
        """Save embeddings to cache file."""
        try:
            KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump({
                    "content_hash": content_hash,
                    "embeddings": embeddings,
                }, f)
            logger.info(f"Saved {len(embeddings)} embeddings to cache")
        except Exception as e:
            logger.warning(f"Failed to save embeddings cache: {e}")

    # ------------------------------------------------------------------
    # Initialization (called once at startup)
    # ------------------------------------------------------------------

    async def initialize(self):
        """Load knowledge base, compute embeddings, prepare for search."""
        if self._initialized:
            return

        try:
            # Load and chunk all YAML files
            faq_data = self._load_yaml("faq.yaml")
            features_data = self._load_yaml("features.yaml")
            videos_data = self._load_yaml("videos.yaml")
            pages_data = self._load_yaml("pages.yaml")

            all_chunks = (
                self._chunk_faq(faq_data)
                + self._chunk_features(features_data)
                + self._chunk_videos(videos_data)
                + self._chunk_pages(pages_data)
            )

            if not all_chunks:
                logger.warning("No knowledge base chunks found — chatbot will have no context")
                self._initialized = True
                return

            # Check cache
            content_hash = self._compute_content_hash()
            cached_embeddings = self._load_cache(content_hash)

            if cached_embeddings and len(cached_embeddings) == len(all_chunks):
                embeddings = cached_embeddings
            else:
                # Compute embeddings via OpenAI
                from app.core.config import settings
                import openai

                client = openai.OpenAI(api_key=settings.openai_api_key)
                texts = [chunk["text"] for chunk in all_chunks]

                # Batch in groups of 100 (API limit is 2048)
                embeddings = []
                batch_size = 100
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    response = client.embeddings.create(
                        model="text-embedding-3-small",
                        input=batch,
                    )
                    embeddings.extend([item.embedding for item in response.data])
                    logger.info(
                        f"Computed embeddings batch {i // batch_size + 1}/"
                        f"{(len(texts) - 1) // batch_size + 1}"
                    )

                self._save_cache(content_hash, embeddings)

            # Store chunks with embeddings
            for i, chunk in enumerate(all_chunks):
                chunk["embedding"] = np.array(embeddings[i], dtype=np.float32)

            self.chunks = all_chunks
            self._initialized = True
            logger.info(f"Help embedding service initialized with {len(self.chunks)} chunks")

        except Exception as e:
            logger.error(f"Failed to initialize help embedding service: {e}")
            self._initialized = True  # Mark as initialized to prevent retry loops

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    def search(
        self, query: str, top_k: int = 5, role_filter: Optional[str] = None
    ) -> list[ChunkResult]:
        """Search for relevant chunks using cosine similarity."""
        if not self.chunks:
            return []

        try:
            from app.core.config import settings
            import openai

            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=[query],
            )
            query_embedding = np.array(response.data[0].embedding, dtype=np.float32)

            # Cosine similarity
            results = []
            for chunk in self.chunks:
                # Optional role filtering
                if role_filter:
                    chunk_roles = chunk.get("metadata", {}).get("roles", [])
                    if chunk_roles and role_filter not in chunk_roles:
                        continue

                chunk_emb = chunk["embedding"]
                similarity = float(
                    np.dot(query_embedding, chunk_emb)
                    / (np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb) + 1e-8)
                )
                results.append(
                    ChunkResult(
                        text=chunk["text"],
                        source=chunk["source"],
                        source_id=chunk["source_id"],
                        metadata=chunk["metadata"],
                        score=similarity,
                    )
                )

            # Sort by score descending and return top_k
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"Embedding search failed: {e}")
            return []


# Singleton instance
help_embedding_service = HelpEmbeddingService()
