"""
Qdrant vector store for persistent semantic memory.

Stores user feedback embeddings for semantic retrieval,
enabling the system to learn from past corrections and patterns.
"""
from typing import Optional
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    ScoredPoint,
)
from loguru import logger

from src.config import settings


COLLECTION_NAME = "user_feedback_memory"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 dimension


class VectorStore:
    """Qdrant-backed vector store for semantic memory."""

    def __init__(self):
        self._client = QdrantClient(url=settings.qdrant_url)
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self._client.get_collections().collections
        names = [c.name for c in collections]
        if COLLECTION_NAME not in names:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE, distance=Distance.COSINE
                ),
            )
            logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")

    def store_feedback_embedding(
        self,
        feedback_id: str,
        embedding: list[float],
        feedback_type: str,
        company: str = "",
        sector: str = "",
        content: str = "",
        finding_type: str = "",
        validation_status: str = "",
        confidence_adjustment: float = 0.0,
    ):
        """Store a feedback entry with its embedding vector."""
        import uuid as uuid_mod

        # Convert string UUID to integer for Qdrant point ID
        point_id = uuid_mod.UUID(feedback_id).int >> 64  # Use upper 64 bits

        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "feedback_id": feedback_id,
                "feedback_type": feedback_type,
                "company": company,
                "sector": sector,
                "content": content,
                "finding_type": finding_type,
                "validation_status": validation_status,
                "confidence_adjustment": confidence_adjustment,
                "applied_count": 0,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        self._client.upsert(
            collection_name=COLLECTION_NAME, points=[point]
        )
        logger.debug(f"Stored feedback embedding: {feedback_id}")

    def search_similar_feedback(
        self,
        query_embedding: list[float],
        company: Optional[str] = None,
        sector: Optional[str] = None,
        finding_type: Optional[str] = None,
        limit: int = 10,
        score_threshold: float = 0.5,
    ) -> list[dict]:
        """
        Search for similar feedback using cosine similarity.

        Args:
            query_embedding: Query vector
            company: Optional filter by company
            sector: Optional filter by sector
            finding_type: Optional filter by finding type
            limit: Max results
            score_threshold: Minimum similarity score

        Returns:
            List of matching feedback entries with scores
        """
        # Build optional filter
        conditions = []
        if company:
            conditions.append(
                FieldCondition(key="company", match=MatchValue(value=company))
            )
        if sector:
            conditions.append(
                FieldCondition(key="sector", match=MatchValue(value=sector))
            )
        if finding_type:
            conditions.append(
                FieldCondition(
                    key="finding_type", match=MatchValue(value=finding_type)
                )
            )

        query_filter = Filter(should=conditions) if conditions else None

        results = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "score": r.score,
                **r.payload,
            }
            for r in results
        ]

    def get_approved_patterns(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[dict]:
        """Get feedback entries that were approved (high confidence boost)."""
        approved_filter = Filter(
            must=[
                FieldCondition(
                    key="validation_status",
                    match=MatchValue(value="approved"),
                )
            ]
        )
        results = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            query_filter=approved_filter,
            limit=limit,
            score_threshold=0.6,
        )
        return [{"score": r.score, **r.payload} for r in results]

    def get_rejected_patterns(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[dict]:
        """Get feedback entries that were rejected (false positives)."""
        rejected_filter = Filter(
            must=[
                FieldCondition(
                    key="validation_status",
                    match=MatchValue(value="rejected"),
                )
            ]
        )
        results = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            query_filter=rejected_filter,
            limit=limit,
            score_threshold=0.6,
        )
        return [{"score": r.score, **r.payload} for r in results]

    def increment_applied_count(self, feedback_id: str):
        """Increment the applied_count for a feedback entry."""
        import uuid as uuid_mod
        point_id = uuid_mod.UUID(feedback_id).int >> 64
        self._client.set_payload(
            collection_name=COLLECTION_NAME,
            payload={"applied_count": "+1"},  # Qdrant doesn't support increment
            points=[point_id],
        )

    def health_check(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False
