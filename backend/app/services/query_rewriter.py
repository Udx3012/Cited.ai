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

from __future__ import annotations
import re
import time
import httpx
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict

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

# Anaphoric references and pronouns that require resolution from conversation context
_ANAPHORA_PATTERNS = re.compile(
    r"\b(it|its|they|their|them|that|this|these|those|former|latter|second|first|last|previous|above|same|there|here)\b",
    re.IGNORECASE,
)

# Follow-up openers that indicate continuation of previous topic
_FOLLOWUP_PATTERNS = re.compile(
    r"^(and |also |what about |how about |why |who |what if |where |explain that|tell me more)",
    re.IGNORECASE,
)

# Minimum word count below which rewriting adds no value (without history)
_MIN_WORDS_FOR_REWRITE = 3
# Queries longer than this are almost certainly well-formed enough
_MAX_WORDS_FOR_REWRITE = 25


def _count_words(text: str) -> int:
    return len(text.split())


def _is_well_formed(query: str, has_history: bool = False) -> bool:
    """
    Returns True when the query is already suitable for retrieval and
    rewriting would add no value. Checks:
    1. If conversation history is present, ensures anaphora or follow-up queries get rewritten.
    2. 3+ meaningful words with no conversational opener or pronoun.
    3. Already a clean keyword phrase (e.g. "Basel III capital adequacy ratio").
    """
    q = query.strip()
    word_count = _count_words(q)

    # When history exists, contextual follow-ups must be resolved
    if has_history:
        if _ANAPHORA_PATTERNS.search(q) or _FOLLOWUP_PATTERNS.search(q) or word_count <= 4:
            return False

    # Very short — rewriting rarely helps without history
    if word_count < _MIN_WORDS_FOR_REWRITE:
        return True

    # Very long — user has already been specific
    if word_count > _MAX_WORDS_FOR_REWRITE:
        return True

    # Has a conversational opener or pronoun — candidate for rewriting
    if _CONVERSATIONAL_OPENERS.match(q) or _ANAPHORA_PATTERNS.search(q) or _FOLLOWUP_PATTERNS.search(q):
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
    "Your task is to rewrite the user's latest query into a concise, standalone, "
    "retrieval-optimized form that maximizes recall from a vector + BM25 hybrid index.\n\n"
    "Rules:\n"
    "- If prior conversation turns are provided, resolve all pronouns ('it', 'that', 'they', 'the former') "
    "and implicit references to prior context so the rewritten query is completely self-contained.\n"
    "- Output ONLY the rewritten query. No explanation, no preamble, no quotes.\n"
    "- Keep it between 4 and 25 words.\n"
    "- Use noun phrases and key domain terms instead of conversational language.\n"
    "- Preserve all named entities, dates, numbers, and specific terminology from the query and context.\n"
    "- If the query is already optimal and self-contained, output it unchanged.\n"
    "- Never invent facts or add topics not implied by the query or history."
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

    async def rewrite(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> QueryRewriteResult:
        """
        Attempt to rewrite *query* into a retrieval-optimized form.
        If *history* is provided (list of dicts with role and content),
        the rewriter uses prior context to resolve anaphoric and conversational references.

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

        # Filter meaningful history (ignore empty turns)
        valid_history = [h for h in (history or []) if h.get("content", "").strip()]
        has_history = len(valid_history) > 0

        # -- Guard: well-formed heuristic --
        if _is_well_formed(query, has_history=has_history):
            return self._passthrough(query, t0, skip_reason="well_formed")

        # -- Attempt LLM rewrite --
        return await self._call_groq(query, t0, history=valid_history if has_history else None)

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

    async def _call_groq(self, query: str, t0: float, history: Optional[List[Dict[str, str]]] = None) -> QueryRewriteResult:
        """
        Call Groq with a fast small model to produce the rewritten query.
        Returns a passthrough result on any error or timeout.
        """
        model = getattr(settings, "QUERY_REWRITER_MODEL", "qwen/qwen3.8-27b")

        user_prompt = query
        if history:
            history_lines = []
            for item in history[-4:]:
                r = item.get("role", "user").capitalize()
                c = item.get("content", "").strip()
                history_lines.append(f"{r}: {c}")
            history_str = "\n".join(history_lines)
            user_prompt = (
                f"Conversation history:\n{history_str}\n\n"
                f"Latest user query: {query}\n\n"
                "Rewrite the latest user query into a single standalone search query:"
            )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
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
