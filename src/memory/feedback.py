"""
Feedback memory — orchestrates storing and retrieving feedback
across PostgreSQL (structured) and Qdrant (semantic) layers.
"""
from typing import Optional

from loguru import logger

from src.storage.postgres import PostgresManager
from src.memory.vector_store import VectorStore


class EmbeddingGenerator:
    """
    Generate text embeddings using sentence-transformers.
    Uses all-MiniLM-L6-v2 (384 dim) — free, fast, runs locally.
    """

    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded embedding model: all-MiniLM-L6-v2")

    def embed(self, text: str) -> list[float]:
        self._load_model()
        return self._model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        return [e.tolist() for e in self._model.encode(texts)]


class FeedbackMemory:
    """
    Manages feedback storage and retrieval across both
    PostgreSQL (structured queries) and Qdrant (semantic search).
    """

    def __init__(
        self,
        postgres: PostgresManager,
        vector_store: VectorStore,
        embedder: Optional[EmbeddingGenerator] = None,
    ):
        self.pg = postgres
        self.qdrant = vector_store
        self.embedder = embedder or EmbeddingGenerator()

    def store_feedback(
        self,
        feedback_type: str,
        content: str,
        finding_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        user_id: str = "default",
        company_ticker: str = "",
        sector: str = "",
        agent_name: str = "",
        finding_type: str = "",
        status: str = "",
        reasoning: str = "",
        confidence_adjustment: float = 0.0,
        apply_to_future: bool = False,
        metadata: dict = None,
    ) -> str:
        """
        Store feedback in both PostgreSQL and Qdrant.

        Returns:
            feedback_id
        """
        # 1. Store in PostgreSQL
        feedback_id = self.pg.store_feedback(
            feedback_type=feedback_type,
            content=content,
            finding_id=finding_id,
            analysis_id=analysis_id,
            user_id=user_id,
            company_ticker=company_ticker,
            sector=sector,
            agent_name=agent_name,
            finding_type=finding_type,
            status=status,
            reasoning=reasoning,
            confidence_adjustment=confidence_adjustment,
            apply_to_future=apply_to_future,
            metadata=metadata,
        )

        # 2. Generate embedding and store in Qdrant (for future retrieval)
        if apply_to_future:
            try:
                embed_text = (
                    f"{feedback_type}: {company_ticker} {sector} "
                    f"{finding_type} - {content}"
                )
                embedding = self.embedder.embed(embed_text)

                self.qdrant.store_feedback_embedding(
                    feedback_id=feedback_id,
                    embedding=embedding,
                    feedback_type=feedback_type,
                    company=company_ticker,
                    sector=sector,
                    content=content,
                    finding_type=finding_type,
                    validation_status=status,
                    confidence_adjustment=confidence_adjustment,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to store feedback embedding in Qdrant: {e}. "
                    "PostgreSQL record still saved."
                )

        return feedback_id

    def retrieve_relevant_feedback(
        self,
        company: str,
        sector: str,
        finding_type: str = "all",
    ) -> dict:
        """
        Retrieve relevant past feedback for an analysis context.

        Returns:
            dict with company_specific, sector_patterns, and
            validation_history keys
        """
        query_text = f"{company} {sector} {finding_type} forensic analysis"
        try:
            embedding = self.embedder.embed(query_text)
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            return self._empty_context()

        # Semantic search in Qdrant
        try:
            company_feedback = self.qdrant.search_similar_feedback(
                query_embedding=embedding,
                company=company,
                limit=5,
            )
            sector_feedback = self.qdrant.search_similar_feedback(
                query_embedding=embedding,
                sector=sector,
                limit=5,
            )
            approved = self.qdrant.get_approved_patterns(
                query_embedding=embedding, limit=5
            )
            rejected = self.qdrant.get_rejected_patterns(
                query_embedding=embedding, limit=5
            )
        except Exception as e:
            logger.warning(f"Qdrant search failed: {e}")
            return self._empty_context()

        return {
            "company_specific_insights": company_feedback,
            "sector_patterns": sector_feedback,
            "approved_patterns": approved,
            "rejected_patterns": rejected,
        }

    def format_memory_context(self, memory_data: dict) -> str:
        """Format retrieved memory into text for prompt injection."""
        parts = []

        if memory_data.get("company_specific_insights"):
            parts.append("### Past Feedback for This Company:")
            for fb in memory_data["company_specific_insights"][:3]:
                parts.append(
                    f"- [{fb.get('validation_status', 'N/A')}] "
                    f"{fb.get('content', '')[:200]}"
                )

        if memory_data.get("sector_patterns"):
            parts.append("\n### Sector-Specific Patterns:")
            for fb in memory_data["sector_patterns"][:3]:
                parts.append(f"- {fb.get('content', '')[:200]}")

        if memory_data.get("rejected_patterns"):
            parts.append(
                "\n### Previously Rejected Findings (avoid similar):"
            )
            for fb in memory_data["rejected_patterns"][:3]:
                parts.append(f"- {fb.get('content', '')[:150]}")

        return "\n".join(parts) if parts else "No prior feedback available."

    @staticmethod
    def _empty_context() -> dict:
        return {
            "company_specific_insights": [],
            "sector_patterns": [],
            "approved_patterns": [],
            "rejected_patterns": [],
        }
