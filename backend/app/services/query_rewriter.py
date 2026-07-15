"""
QueryRewriter — intelligent pre-retrieval query reformulation service.

Rewrites ambiguous, incomplete, or conversational queries into dense,
retrieval-optimized forms before they reach the embedding + BM25 pipeline.

Design principles:
- Model-agnostic: swap the underlying LLM via QUERY_REWRITER_MODEL config key.
- Fail-safe: all failures fall back silently to the original query.
- Efficient: skip heuristics avoid Groq calls for already-good queries.
- Observable: every result carries timing and a was_rewritten flag.
"""

import re
import time
import httpx
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class QueryRewriteResult:
    """Carries the original and rewritten query plus observability fields."""
    original_query: str
    rewritten_query: str           # equals original_query when not rewritten
    was_rewritten: bool
    latency_ms: int
    skip_reason: Optional[str] = None  # populated when skipping, e.g. "well_formed"


# ---------------------------------------------------------------------------
# Skip-heuristic patterns
# ---------------------------------------------------------------------------

# Conversational openers that signal the query needs rewriting
_CONVERSATIONAL_OPENERS = re.compile(
    r"^(can you |could you |please |i want to |i need |tell me |i was wondering |"
    r"do you know |what('s| is) |how (do|does|can|should) |"
    r"explain |describe |give me |show me |find me )",
    re.IGNORECASE,
)

# Queries already phrased as noun-phrase / keyword clusters need no rewrite
_WELL_FORMED_PATTERN = re.compile(
    r"^[A-Z][a-zA-Z\s\-,]+(\?)?$"  # Title-cased or question ending
)

# Minimum word count below which rewriting adds no value
_MIN_WORDS_FOR_REWRITE = 3
# Queries longer than this are almost certainly well-formed enough
_MAX_WORDS_FOR_REWRITE = 25


def _count_words(text: str) -> int:
    return len(text.split())


def _is_well_formed(query: str) -> bool:
    """
    Returns True when the query is already suitable for retrieval and
    rewriting would add no value. Checks:
    1. 4+ meaningful words with no conversational opener.
    2. Already a clean keyword phrase (e.g. "Basel III capital adequacy ratio").
    """
    q = query.strip()
    word_count = _count_words(q)

    # Very short — rewriting rarely helps
    if word_count < _MIN_WORDS_FOR_REWRITE:
        return True

    # Very long — user has already been specific
    if word_count > _MAX_WORDS_FOR_REWRITE:
        return True

    # Has a conversational opener — candidate for rewriting
    if _CONVERSATIONAL_OPENERS.match(q):
        return False

    # No conversational opener and ≥3 words → treat as well-formed
    if word_count >= 3:
        return True

    return False


# ---------------------------------------------------------------------------
# Rewriter system prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a search query optimizer for a document retrieval system. "
    "Your only task is to rewrite the user's query into a concise, "
    "retrieval-optimized form that maximizes recall from a vector + BM25 hybrid index.\n\n"
    "Rules:\n"
    "- Output ONLY the rewritten query. No explanation, no preamble, no quotes.\n"
    "- Keep it between 5 and 20 words.\n"
    "- Use noun phrases and key domain terms instead of conversational language.\n"
    "- Preserve all named entities, dates, and numbers from the original.\n"
    "- If the query is already optimal for retrieval, output it unchanged.\n"
    "- Never invent facts or add topics not implied by the original query."
)


# ---------------------------------------------------------------------------
# QueryRewriter service
# ---------------------------------------------------------------------------

class QueryRewriter:
    """
    Modular pre-retrieval query rewriting service.

    Usage:
        result = await query_rewriter.rewrite("can you tell me about risks?")
        # result.rewritten_query → "risk factors and risk management strategies"
        # result.was_rewritten   → True
        # result.latency_ms      → 312
    """

    def __init__(self) -> None:
        self._api_url = "https://api.groq.com/openai/v1/chat/completions"
        self._headers: dict = {}   # built lazily so hot-reload picks up key changes
        self._client = httpx.AsyncClient()

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def rewrite(self, query: str) -> QueryRewriteResult:
        """
        Attempt to rewrite *query* into a retrieval-optimized form.

        Skip conditions (no Groq call, returns immediately):
        - Feature disabled via QUERY_REWRITER_ENABLED=False.
        - GROQ_API_KEY is not configured.
        - Query is a greeting / chit-chat (detected by is_general_chat import).
        - Query already passes the well-formed heuristic.

        Fallback on Groq failure:
        - Returns original query with was_rewritten=False.
        """
        t0 = time.perf_counter()

        # -- Guard: feature toggle --
        if not getattr(settings, "QUERY_REWRITER_ENABLED", True):
            return self._passthrough(query, t0, skip_reason="disabled")

        # -- Guard: no API key --
        if not settings.GROQ_API_KEY:
            return self._passthrough(query, t0, skip_reason="no_api_key")

        # -- Guard: general chat (import here to avoid circular import) --
        try:
            from app.api.endpoints.chat import is_general_chat
            if is_general_chat(query):
                return self._passthrough(query, t0, skip_reason="general_chat")
        except ImportError:
            pass

        # -- Guard: well-formed heuristic --
        if _is_well_formed(query):
            return self._passthrough(query, t0, skip_reason="well_formed")

        # -- Attempt LLM rewrite --
        return await self._call_groq(query, t0)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _passthrough(self, query: str, t0: float, skip_reason: str) -> QueryRewriteResult:
        latency = int((time.perf_counter() - t0) * 1000)
        logger.debug(f"QueryRewriter: skipping rewrite — reason={skip_reason}, latency={latency}ms")
        return QueryRewriteResult(
            original_query=query,
            rewritten_query=query,
            was_rewritten=False,
            latency_ms=latency,
            skip_reason=skip_reason,
        )

    async def _call_groq(self, query: str, t0: float) -> QueryRewriteResult:
        """
        Call Groq with a fast small model to produce the rewritten query.
        Returns a passthrough result on any error or timeout.
        """
        model = getattr(settings, "QUERY_REWRITER_MODEL", "llama-3.1-8b-instant")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            "temperature": 0.0,
            "max_tokens": 80,
        }

        try:
            response = await self._client.post(
                self._api_url,
                json=payload,
                headers=self._get_headers(),
                timeout=5.0,  # hard 5-second ceiling
            )

            if response.status_code != 200:
                logger.warning(
                    f"QueryRewriter: Groq returned HTTP {response.status_code}. "
                    "Falling back to original query."
                )
                return self._passthrough(query, t0, skip_reason="groq_error")

            raw = response.json()["choices"][0]["message"]["content"].strip()

            # Sanitize: strip surrounding quotes the model sometimes adds
            rewritten = raw.strip("\"'")

            latency = int((time.perf_counter() - t0) * 1000)

            # If the model echoed back the same text or returned nothing, mark as not rewritten
            was_rewritten = bool(rewritten) and rewritten.lower() != query.lower()

            logger.info(
                f"QueryRewriter: '{query}' → '{rewritten}' "
                f"(was_rewritten={was_rewritten}, latency={latency}ms, model={model})"
            )

            return QueryRewriteResult(
                original_query=query,
                rewritten_query=rewritten if was_rewritten else query,
                was_rewritten=was_rewritten,
                latency_ms=latency,
                skip_reason=None,
            )

        except httpx.TimeoutException:
            logger.warning("QueryRewriter: Groq call timed out (>5s). Using original query.")
            return self._passthrough(query, t0, skip_reason="timeout")
        except Exception as exc:
            logger.error(f"QueryRewriter: Unexpected error — {exc}. Using original query.")
            return self._passthrough(query, t0, skip_reason="error")


# ---------------------------------------------------------------------------
# Exported singleton
# ---------------------------------------------------------------------------

query_rewriter = QueryRewriter()
