"""
Redis cache layer for session state and data caching.
"""
import json
from typing import Optional

import redis
from loguru import logger

from src.config import settings


class RedisCache:
    """Redis-backed cache for session state and transient data."""

    def __init__(self):
        self._client = redis.from_url(
            settings.redis_url, decode_responses=True
        )

    # ---- Session State ----

    def set_session_state(
        self, session_id: str, state: dict, ttl: int = 14400
    ):
        """Store workflow session state. Default TTL: 4 hours."""
        key = f"session:{session_id}:state"
        self._client.setex(key, ttl, json.dumps(state, default=str))

    def get_session_state(self, session_id: str) -> Optional[dict]:
        """Retrieve workflow session state."""
        key = f"session:{session_id}:state"
        data = self._client.get(key)
        return json.loads(data) if data else None

    def delete_session_state(self, session_id: str):
        self._client.delete(f"session:{session_id}:state")

    # ---- Data Cache ----

    def cache_company_data(
        self, ticker: str, data: dict, ttl: int = 86400
    ):
        """Cache fetched company data. Default TTL: 24 hours."""
        key = f"data:{ticker}"
        self._client.setex(key, ttl, json.dumps(data, default=str))

    def get_cached_company_data(self, ticker: str) -> Optional[dict]:
        """Get cached company data if available."""
        key = f"data:{ticker}"
        data = self._client.get(key)
        return json.loads(data) if data else None

    # ---- Memory Cache ----

    def cache_memory_result(
        self, company: str, finding_type: str, results: list, ttl: int = 3600
    ):
        """Cache memory retrieval results. Default TTL: 1 hour."""
        key = f"memory:{company}:{finding_type}"
        self._client.setex(key, ttl, json.dumps(results, default=str))

    def get_cached_memory(
        self, company: str, finding_type: str
    ) -> Optional[list]:
        key = f"memory:{company}:{finding_type}"
        data = self._client.get(key)
        return json.loads(data) if data else None

    def invalidate_memory_cache(self, company: str):
        """Invalidate all memory caches for a company."""
        pattern = f"memory:{company}:*"
        keys = self._client.keys(pattern)
        if keys:
            self._client.delete(*keys)

    # ---- Analysis Progress ----

    def set_analysis_progress(
        self, analysis_id: str, progress: dict
    ):
        """Store real-time analysis progress for UI streaming."""
        key = f"progress:{analysis_id}"
        self._client.setex(key, 7200, json.dumps(progress, default=str))

    def get_analysis_progress(self, analysis_id: str) -> Optional[dict]:
        key = f"progress:{analysis_id}"
        data = self._client.get(key)
        return json.loads(data) if data else None

    # ---- Utilities ----

    def health_check(self) -> bool:
        try:
            return self._client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
