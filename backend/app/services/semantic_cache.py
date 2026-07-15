import time
import logging
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache Entry structures
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    original_query: str
    embedding: List[float]
    created_at: float
    latency_ms: int
    
    # Endpoint payload types: "search" | "chat"
    entry_type: str
    
    # Cached payload fields
    rewritten_query: Optional[str] = None
    was_rewritten: bool = False
    
    # For "search" responses: list of dict chunk matches
    results: Optional[List[Dict[str, Any]]] = None
    
    # For "chat" responses: generated answers and citations
    answer: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    confidence_score: float = 0.0
    sufficient_context: bool = False


# ---------------------------------------------------------------------------
# Cosine Similarity Helper
# ---------------------------------------------------------------------------

def calculate_cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
        
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = sum(a * a for a in v1) ** 0.5
    norm_v2 = sum(b * b for b in v2) ** 0.5
    
    if norm_v1 == 0.0 or norm_v2 == 0.0:
        return 0.0
        
    return dot_product / (norm_v1 * norm_v2)


# ---------------------------------------------------------------------------
# SemanticCache Service
# ---------------------------------------------------------------------------

class SemanticCache:
    """
    In-memory semantic cache using embedding cosine similarity.
    Provides thread-safe read/write operations and cache statistics.
    """
    def __init__(self) -> None:
        self._cache: List[CacheEntry] = []
        self._lock = threading.Lock()
        
        # Statistics counters
        self._hits = 0
        self._misses = 0
        self._total_saved_latency_ms = 0.0

    # ------------------------------------------------------------------
    # Cache Lookup
    # ------------------------------------------------------------------

    def get(self, query: str, query_embedding: List[float], entry_type: str) -> Optional[CacheEntry]:
        """
        Looks up a semantically similar query of `entry_type` in the cache.
        Returns the match if similarity exceeds the threshold and the entry is not expired.
        """
        if not settings.CACHE_ENABLED:
            return None

        now = time.time()
        ttl = settings.CACHE_TTL_SECONDS
        threshold = settings.CACHE_SIMILARITY_THRESHOLD

        with self._lock:
            # 1. Clean expired entries
            expired_indices = []
            for idx, entry in enumerate(self._cache):
                if now - entry.created_at > ttl:
                    expired_indices.append(idx)
            
            # Delete expired in reverse order to keep indices correct
            for idx in sorted(expired_indices, reverse=True):
                logger.debug(f"SemanticCache: Evicting expired query: '{self._cache[idx].original_query}'")
                self._cache.pop(idx)

            # 2. Search for the closest semantic match
            best_match: Optional[CacheEntry] = None
            best_similarity = -1.0

            for entry in self._cache:
                if entry.entry_type != entry_type:
                    continue

                similarity = calculate_cosine_similarity(query_embedding, entry.embedding)
                if similarity >= threshold and similarity > best_similarity:
                    best_match = entry
                    best_similarity = similarity

            if best_match:
                self._hits += 1
                self._total_saved_latency_ms += best_match.latency_ms
                logger.info(
                    f"SemanticCache: HIT for query='{query}' matched against cached_query='{best_match.original_query}' "
                    f"(similarity={best_similarity:.4f}, saved={best_match.latency_ms}ms)"
                )
                return best_match

            self._misses += 1
            logger.debug(f"SemanticCache: MISS for query='{query}'")
            return None

    # ------------------------------------------------------------------
    # Cache Store
    # ------------------------------------------------------------------

    def set(
        self,
        query: str,
        query_embedding: List[float],
        entry_type: str,
        latency_ms: int,
        rewritten_query: Optional[str] = None,
        was_rewritten: bool = False,
        results: Optional[List[Dict[str, Any]]] = None,
        answer: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        confidence_score: float = 0.0,
        sufficient_context: bool = False,
    ) -> None:
        """Stores a query, its embedding, and the generated execution results in the cache."""
        if not settings.CACHE_ENABLED:
            return

        new_entry = CacheEntry(
            original_query=query,
            embedding=query_embedding,
            created_at=time.time(),
            latency_ms=latency_ms,
            entry_type=entry_type,
            rewritten_query=rewritten_query,
            was_rewritten=was_rewritten,
            results=results,
            answer=answer,
            citations=citations,
            confidence_score=confidence_score,
            sufficient_context=sufficient_context,
        )

        with self._lock:
            self._cache.append(new_entry)
            logger.info(f"SemanticCache: Cached new entry for query='{query}' (type={entry_type}, latency={latency_ms}ms)")

    # ------------------------------------------------------------------
    # Invalidation & Stats
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Purges all entries from the semantic cache."""
        with self._lock:
            size = len(self._cache)
            self._cache.clear()
            logger.info(f"SemanticCache: Cache cleared successfully (purged {size} entries).")

    def get_stats(self) -> Dict[str, Any]:
        """Returns runtime performance statistics of the cache."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0.0
            miss_rate = (self._misses / total_requests) if total_requests > 0 else 0.0
            avg_saved = (self._total_saved_latency_ms / self._hits) if self._hits > 0 else 0.0
            
            return {
                "hit_rate": float(hit_rate),
                "miss_rate": float(miss_rate),
                "avg_latency_saved_ms": float(avg_saved),
                "total_hits": int(self._hits),
                "total_misses": int(self._misses),
            }


# Export default instanced service
semantic_cache = SemanticCache()
