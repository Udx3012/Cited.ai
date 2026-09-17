from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import asyncio
import time
import json
import logging
from typing import List, Dict, Any
from app.schemas.chat import ChatRequest, ChatResponse, CitationMeta
from app.schemas.retrieval import CacheStatsResponse
from app.embeddings.embedder import hf_embedder
from app.services.qdrant import qdrant_service
from app.retrieval.bm25 import bm25_service
from app.retrieval.fusion import ReciprocalRankFusion
from app.reranker.rerank import hf_reranker
from app.services.groq import groq_service
from app.services.gemini import gemini_service
from app.services.query_rewriter import query_rewriter
from app.services.semantic_cache import semantic_cache

logger = logging.getLogger(__name__)
router = APIRouter()

def _validate_citations(raw_citations: List[Dict[str, Any]], context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validates citation indices against returned context chunks, ensures matched_text
    is populated from chunk content, and enriches records with retrieval scores.
    """
    validated = []
    for c in raw_citations:
        cit_id = c.get("id")
        if isinstance(cit_id, int) and 1 <= cit_id <= len(context_chunks):
            chunk = context_chunks[cit_id - 1]
            doc_name = chunk.get("document_name") or chunk.get("metadata", {}).get("document_name", "unknown")
            page_num = chunk.get("page") or chunk.get("page_number") or chunk.get("metadata", {}).get("page", 1)
            chunk_txt = chunk.get("text", "")
            
            matched = c.get("matched_text")
            if not matched or len(matched.strip()) < 10:
                matched = chunk_txt[:200]
            
            validated.append({
                "id": cit_id,
                "source": doc_name,
                "page": page_num,
                "chunk": chunk.get("chunk_index", 0),
                "matched_text": matched,
                "vector_score": float(chunk.get("vector_score", 0.0)),
                "bm25_score": float(chunk.get("bm25_score", 0.0)),
                "rerank_score": float(chunk.get("rerank_score", 0.0))
            })
    return validated

def is_general_chat(query_text: str) -> bool:
    """
    Returns True if the query is a greeting, farewell, gratitude, chit-chat,
    identity question, or app-meta question that does NOT target document contents.

    Handles:
    - Exact match greetings / farewells / gratitude / identity ("hello", "thanks", "who are you")
    - Short (<=2 word) queries consisting purely of greeting/gratitude/farewell tokens ("hey there", "thank you")
    - Greeting-prefixed pure chit-chat ("hey, how are you", "hello who are you")
    - App-capability questions ("how do i upload a doc?", "what formats are supported?")
    """
    import re
    q = query_text.strip().lower()
    q_stripped = q.rstrip("?.-!,;:")

    greeting_tokens = {"hi", "hello", "hey", "hola", "greetings", "howdy", "yo", "sup"}
    farewell_tokens = {"bye", "goodbye", "farewell", "cya"}
    gratitude_tokens = {"thanks", "thank"}

    greetings = greeting_tokens | {"good morning", "good afternoon", "good evening", "hi there", "hello there", "what's up", "whats up"}
    farewells  = farewell_tokens | {"see you"}
    gratitude  = {"thanks", "thank you", "thank you so much", "perfect thanks", "ok thanks", "great thanks"}
    chitchat   = {"how are you", "how's it going", "hows it going", "how are you doing", "what's new", "whats new"}
    identity   = {
        "who are you", "what is your name", "tell me about yourself",
        "what do you do", "what are you", "who created you", "who made you",
        "what is cited.ai", "what is cited"
    }

    # 1. Exact match
    if q_stripped in greetings | farewells | gratitude | chitchat | identity:
        return True

    # 2. Short query (<=2 words) consisting solely of greeting/farewell/gratitude tokens
    words = [w.strip("?.-!,;:") for w in q_stripped.split() if w.strip("?.-!,;:")]
    if 1 <= len(words) <= 2:
        valid_short_tokens = greeting_tokens | farewell_tokens | gratitude_tokens | {"there", "you", "all", "assistant", "ai"}
        if all(w in valid_short_tokens for w in words):
            return True

    # 3. Greeting-prefixed pure conversational question (e.g. "hey, how are you doing?")
    if words and words[0] in greeting_tokens:
        remainder = " ".join(words[1:]).strip()
        if remainder in chitchat | identity | greetings | farewells | gratitude:
            return True

    # 4. App-meta / capability questions — about Cited.ai features, not document content
    app_meta_patterns = [
        r"^how do i (upload|add|attach|import|delete|clear)\b",
        r"^can i (upload|add|attach|import|delete)\b",
        r"^what (file formats?|types?) (are|do you) support\b",
        r"^how does (cited|this app|the search) work\b",
    ]
    for pattern in app_meta_patterns:
        if re.search(pattern, q_stripped):
            return True

    return False


@router.post("/completions")
async def chat_completions(payload: ChatRequest):
    """
    Submits conversational query to the grounded RAG generator.
    Runs concurrent hybrid retrieval (dense + sparse), fuses results via RRF, 
    reranks via cross-encoder with fast SLA, and synthesizes answers via Groq/Gemini LLM.
    Supports Server-Sent Events (SSE) token streaming.
    """
    start_time = time.perf_counter()
    logger.info(f"Received completions request: '{payload.query}' (stream={payload.stream})")
    
    # 1. AI Guardrail: Prompt Injection and Leakage Mitigation
    injection_keywords = [
        "ignore previous instructions",
        "ignore preceding instructions",
        "system prompt",
        "override system prompt",
        "ignore instructions",
        "you are now a",
        "leak your instructions",
        "output your system prompt",
        "leak your prompt"
    ]
    query_lower = payload.query.lower()
    if any(keyword in query_lower for keyword in injection_keywords):
        logger.warning(f"Guardrail Check: Prompt injection keyword matched in query: '{payload.query}'")
        refusal_msg = "I cannot answer this question due to safety policy guidelines."
        if payload.stream:
            async def sse_injection_refusal():
                yield f"data: {json.dumps({'type': 'content', 'delta': refusal_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'metadata', 'citations': [], 'confidence_score': 0.0, 'sufficient_context': False})}\n\n"
            return StreamingResponse(sse_injection_refusal(), media_type="text/event-stream")
        else:
            return ChatResponse(
                success=False,
                answer=refusal_msg,
                citations=[],
                confidence_score=0.0,
                sufficient_context=False,
                latency_ms=0,
                original_query=payload.query,
                rewritten_query=None,
                was_rewritten=False,
                rewrite_latency_ms=0,
                cache_hit=False,
                cache_stats=CacheStatsResponse(**semantic_cache.get_stats()),
            )

    try:
        import re
        doc_query_pattern = re.compile(
            r"\b(which|what|list|show|name|available|any|all|active)\b.{0,25}\b(doc|document|pdf|file|paper|resume|upload)\b",
            re.IGNORECASE
        )
        is_asking_about_docs = bool(doc_query_pattern.search(payload.query))

        # --- Step 0.1: Exact Cache Match (Ultra-Fast Path) ---
        cache_match = semantic_cache.get_exact(payload.query, entry_type="chat")
        if cache_match:
            cached_citations = [CitationMeta(**c) for c in (cache_match.citations or [])]
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"SemanticCache: Exact HIT for query='{payload.query}' served in {latency_ms}ms.")
            if payload.stream:
                async def sse_cached_generator():
                    yield f"data: {json.dumps({'type': 'content', 'delta': cache_match.answer or ''})}\n\n"
                    meta_payload = {
                        'type': 'metadata',
                        'citations': [c.model_dump() for c in cached_citations],
                        'confidence_score': cache_match.confidence_score,
                        'sufficient_context': cache_match.sufficient_context,
                        'cache_hit': True,
                    }
                    yield f"data: {json.dumps(meta_payload)}\n\n"
                return StreamingResponse(sse_cached_generator(), media_type="text/event-stream")
            else:
                return ChatResponse(
                    success=True,
                    answer=cache_match.answer or "",
                    citations=cached_citations,
                    confidence_score=cache_match.confidence_score,
                    sufficient_context=cache_match.sufficient_context,
                    latency_ms=latency_ms,
                    original_query=payload.query,
                    rewritten_query=cache_match.rewritten_query if cache_match.was_rewritten else None,
                    was_rewritten=cache_match.was_rewritten,
                    rewrite_latency_ms=0,
                    cache_hit=True,
                    cache_stats=CacheStatsResponse(**semantic_cache.get_stats()),
                )

        history_dicts = [m.model_dump() for m in payload.history] if payload.history else None

        # --- Early Exit: General Chat / Greetings ---
        if is_general_chat(payload.query):
            logger.info("General chat query detected. Skipping retrieval pipeline.")
            context_chunks = []
            if payload.stream:
                async def sse_general_chat_stream():
                    try:
                        async for event in groq_service.generate_grounded_answer_stream(payload.query, context_chunks, history=history_dicts):
                            yield f"data: {json.dumps(event)}\n\n"
                    except Exception as stream_err:
                        logger.warning(f"Groq general chat stream failed: {stream_err}. Failing over to Gemini...")
                        if gemini_service and gemini_service.api_key:
                            async for event in gemini_service.generate_grounded_answer_stream(payload.query, context_chunks, history=history_dicts):
                                yield f"data: {json.dumps(event)}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'content', 'delta': 'Hello! How can I assist you today?'})}\n\n"
                            yield f"data: {json.dumps({'type': 'metadata', 'citations': [], 'confidence_score': 1.0, 'sufficient_context': True})}\n\n"
                return StreamingResponse(sse_general_chat_stream(), media_type="text/event-stream")
            else:
                try:
                    rag_output = await groq_service.generate_grounded_answer(payload.query, context_chunks, history=history_dicts)
                except Exception as groq_err:
                    logger.warning(f"Groq general chat failed: {groq_err}. Failing over to Gemini...")
                    if gemini_service and gemini_service.api_key:
                        rag_output = await gemini_service.generate_grounded_answer(payload.query, context_chunks, history=history_dicts)
                    else:
                        rag_output = {"answer": "Hello! How can I assist you today?", "citations": [], "confidence_score": 1.0, "sufficient_context": True}

                total_latency = int((time.perf_counter() - start_time) * 1000)
                logger.info(f"General chat answered in {total_latency}ms.")
                return ChatResponse(
                    success=True,
                    answer=rag_output.get("answer", ""),
                    citations=[],
                    confidence_score=1.0,
                    sufficient_context=True,
                    latency_ms=total_latency,
                    original_query=payload.query,
                    rewritten_query=None,
                    was_rewritten=False,
                    rewrite_latency_ms=0,
                    cache_hit=False,
                    cache_stats=CacheStatsResponse(**semantic_cache.get_stats()),
                )

        # --- Step 1: Concurrent Pre-Flight Tasks (Embedding + BM25 + Query Rewriter) ---
        rewrite_task = asyncio.create_task(query_rewriter.rewrite(payload.query, history=history_dicts))
        embed_task = asyncio.create_task(hf_embedder.embed_documents([payload.query]))
        bm25_task = asyncio.create_task(asyncio.to_thread(bm25_service.retrieve_sparse, payload.query, 20))

        # Await embedding first to check semantic cache immediately
        query_vector = [0.0] * 1024
        try:
            query_vectors = await embed_task
            if query_vectors:
                query_vector = query_vectors[0]
        except Exception as embed_ex:
            logger.error(f"Failed to generate query embedding: {str(embed_ex)}")

        # --- Step 1.5: Semantic Cache Lookup (Vector Similarity) ---
        if query_vector and any(val != 0.0 for val in query_vector):
            cache_match = semantic_cache.get(payload.query, query_vector, entry_type="chat")
            if cache_match:
                cached_citations = [CitationMeta(**c) for c in (cache_match.citations or [])]
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                logger.info(f"SemanticCache: Vector HIT for query='{payload.query}' served in {latency_ms}ms.")
                if payload.stream:
                    async def sse_cached_generator():
                        yield f"data: {json.dumps({'type': 'content', 'delta': cache_match.answer or ''})}\n\n"
                        meta_payload = {
                            'type': 'metadata',
                            'citations': [c.model_dump() for c in cached_citations],
                            'confidence_score': cache_match.confidence_score,
                            'sufficient_context': cache_match.sufficient_context,
                            'cache_hit': True,
                        }
                        yield f"data: {json.dumps(meta_payload)}\n\n"
                    return StreamingResponse(sse_cached_generator(), media_type="text/event-stream")
                else:
                    return ChatResponse(
                        success=True,
                        answer=cache_match.answer or "",
                        citations=cached_citations,
                        confidence_score=cache_match.confidence_score,
                        sufficient_context=cache_match.sufficient_context,
                        latency_ms=latency_ms,
                        original_query=payload.query,
                        rewritten_query=cache_match.rewritten_query if cache_match.was_rewritten else None,
                        was_rewritten=cache_match.was_rewritten,
                        rewrite_latency_ms=0,
                        cache_hit=True,
                        cache_stats=CacheStatsResponse(**semantic_cache.get_stats()),
                    )

        # Collect rewrite and initial BM25 results
        rewrite_result = await rewrite_task
        retrieval_query = rewrite_result.rewritten_query
        
        # Align dense retrieval vector with rewritten query when rewriting transformed the query
        dense_query_vector = query_vector
        if rewrite_result.was_rewritten and retrieval_query.lower() != payload.query.lower():
            try:
                rewritten_vectors = await hf_embedder.embed_documents([retrieval_query])
                if rewritten_vectors and any(val != 0.0 for val in rewritten_vectors[0]):
                    dense_query_vector = rewritten_vectors[0]
                    logger.info("Dense search aligned with rewritten query embedding.")
            except Exception as e:
                logger.warning(f"Failed to generate rewritten query embedding: {str(e)}")

        sparse_results = []
        try:
            sparse_results = await bm25_task
        except Exception as e:
            logger.error(f"BM25 retrieval failed: {str(e)}")

        # If query was rewritten, expand sparse results with rewritten query
        if rewrite_result.was_rewritten and retrieval_query.lower() != payload.query.lower():
            try:
                additional_sparse = await asyncio.to_thread(bm25_service.retrieve_sparse, retrieval_query, 10)
                existing_ids = {str(c["id"]) for c in sparse_results}
                for c in additional_sparse:
                    if str(c["id"]) not in existing_ids:
                        sparse_results.append(c)
            except Exception as e:
                logger.debug(f"Rewritten BM25 expansion skipped: {str(e)}")

        # Optional document_ids scoping for sparse candidates
        if payload.document_ids:
            target_ids = set(payload.document_ids)
            sparse_results = [
                c for c in sparse_results
                if (c.get("document_id") in target_ids or str(c.get("id", "")).split("_")[0] in target_ids)
            ]

        # --- Step 2: Dense Retrieval (Qdrant Cloud) ---
        dense_results = []
        if qdrant_service.client and any(val != 0.0 for val in dense_query_vector):
            try:
                search_kwargs = {
                    "collection_name": qdrant_service.collection_name,
                    "query": dense_query_vector,
                    "limit": 20,
                    "with_payload": True
                }
                if payload.document_ids:
                    from qdrant_client.models import Filter, FieldCondition, MatchAny
                    search_kwargs["query_filter"] = Filter(
                        must=[FieldCondition(key="document_id", match=MatchAny(any=payload.document_ids))]
                    )

                search_response = await asyncio.to_thread(
                    qdrant_service.client.query_points,
                    **search_kwargs
                )

                for point in search_response.points:
                    payload_data = point.payload or {}
                    doc_name = payload_data.get("document_name", "unknown")
                    page_num = payload_data.get("page_number", 1)
                    chunk_idx = payload_data.get("chunk_index", 0)
                    dense_results.append({
                        "id": str(point.id),
                        "document_name": doc_name,
                        "page": page_num,
                        "page_number": page_num,
                        "chunk_index": chunk_idx,
                        "text": payload_data.get("text", ""),
                        "vector_score": float(point.score),
                        "bm25_score": 0.0,
                        "rerank_score": 0.0,
                        "metadata": {
                            "document_name": doc_name,
                            "page": page_num,
                            "heading": payload_data.get("heading", "Introduction"),
                            "is_ocr": payload_data.get("is_ocr", False)
                        }
                    })
            except Exception as e:
                logger.error(f"Dense vector search failed: {str(e)}")

        # --- Step 3: Hybrid Score Fusion (RRF) ---
        fused_chunks = ReciprocalRankFusion.fuse_results(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=60,
            limit=20,
            dense_weight=payload.dense_weight if payload.dense_weight is not None else 0.5,
            sparse_weight=payload.sparse_weight if payload.sparse_weight is not None else 0.5
        )

        # --- Step 4: Cross-Encoder Reranking with Fast SLA ---
        reranked_chunks = []
        if len(fused_chunks) > 2:
            try:
                reranked_chunks = await asyncio.wait_for(
                    hf_reranker.rerank_chunks(retrieval_query, fused_chunks),
                    timeout=2.5
                )
            except asyncio.TimeoutError:
                logger.warning("Reranker timed out after 2.5s — using RRF order.")
                reranked_chunks = fused_chunks
            except Exception as e:
                logger.warning(f"Reranking error: {str(e)} — using RRF order.")
                reranked_chunks = fused_chunks
        else:
            reranked_chunks = fused_chunks

        # Expanded context window from top-5 to top-8 chunks
        context_chunks = reranked_chunks[:8]

        # Intercept queries asking about what documents are uploaded/active
        uploaded_docs = []
        if is_asking_about_docs:
            uploaded_docs = sorted(list(set(
                c.get("document_name") or c.get("metadata", {}).get("document_name")
                for c in bm25_service.chunks 
                if (c.get("document_name") or c.get("metadata", {}).get("document_name"))
            )))
            if uploaded_docs:
                docs_str = ", ".join(uploaded_docs)
                context_chunks = [{
                    "id": "virtual-docs-info",
                    "document_name": "System Metadata",
                    "page": 1,
                    "page_number": 1,
                    "chunk_index": 0,
                    "text": f"The currently uploaded and active documents in the workspace are: {docs_str}.",
                    "vector_score": 1.0,
                    "bm25_score": 1.0,
                    "rerank_score": 1.0,
                    "reranker_applied": True,
                    "metadata": {
                        "document_name": "System Metadata",
                        "page": 1,
                        "heading": "Active Documents",
                        "is_ocr": False
                    }
                }] + context_chunks[:7]

        # Grounded Refusal Check (Calibrated to prevent false refusals when reranking falls back)
        insufficient_context = False
        if is_asking_about_docs and uploaded_docs:
            insufficient_context = False
        elif not context_chunks:
            insufficient_context = True
        else:
            max_vector_score = max(c.get("vector_score", 0.0) for c in context_chunks)
            max_bm25_score = max(c.get("bm25_score", 0.0) for c in context_chunks)
            max_rerank_score = max(c.get("rerank_score", 0.0) for c in context_chunks)
            reranker_applied = any(c.get("reranker_applied", False) for c in context_chunks)

            if reranker_applied and max_rerank_score >= 0.40:
                insufficient_context = False
            elif max_bm25_score >= 2.0 or max_vector_score >= 0.45:
                insufficient_context = False
            elif max_vector_score < 0.35 and max_bm25_score < 0.4:
                insufficient_context = True

        if insufficient_context:
            logger.info("Guardrail Check: Retrieval confidence below threshold. Refusing query.")
            refusal_text = "Insufficient information found in the uploaded documents."
            if payload.stream:
                async def sse_insufficient_refusal():
                    yield f"data: {json.dumps({'type': 'content', 'delta': refusal_text})}\n\n"
                    yield f"data: {json.dumps({'type': 'metadata', 'citations': [], 'confidence_score': 0.0, 'sufficient_context': False})}\n\n"
                return StreamingResponse(sse_insufficient_refusal(), media_type="text/event-stream")
            else:
                return ChatResponse(
                    success=True,
                    answer=refusal_text,
                    citations=[],
                    confidence_score=0.0,
                    sufficient_context=False,
                    latency_ms=int((time.perf_counter() - start_time) * 1000),
                    original_query=payload.query,
                    rewritten_query=rewrite_result.rewritten_query if rewrite_result.was_rewritten else None,
                    was_rewritten=rewrite_result.was_rewritten,
                    rewrite_latency_ms=rewrite_result.latency_ms,
                    cache_hit=False,
                    cache_stats=CacheStatsResponse(**semantic_cache.get_stats()),
                )

        # --- Step 5: Generation (Groq / Gemini LLM with Failover) ---
        if payload.stream:
            async def sse_event_generator():
                accumulated_answer = ""
                final_meta = {}
                try:
                    # Stream through primary generator with fallback
                    try:
                        async for event in groq_service.generate_grounded_answer_stream(
                            payload.query, context_chunks, history=history_dicts
                        ):
                            if event.get("type") == "content":
                                accumulated_answer += event.get("delta", "")
                            elif event.get("type") == "metadata":
                                event["citations"] = _validate_citations(event.get("citations", []), context_chunks)
                                final_meta = event
                            yield f"data: {json.dumps(event)}\n\n"
                    except Exception as primary_stream_ex:
                        logger.warning(f"Groq streaming failed: {str(primary_stream_ex)}. Failing over to Gemini...")
                        if gemini_service and gemini_service.api_key:
                            async for event in gemini_service.generate_grounded_answer_stream(
                                payload.query, context_chunks, history=history_dicts
                            ):
                                if event.get("type") == "content":
                                    accumulated_answer += event.get("delta", "")
                                elif event.get("type") == "metadata":
                                    event["citations"] = _validate_citations(event.get("citations", []), context_chunks)
                                    final_meta = event
                                yield f"data: {json.dumps(event)}\n\n"
                        else:
                            raise primary_stream_ex

                    # Store streaming results in semantic cache on completion
                    if accumulated_answer and any(val != 0.0 for val in query_vector):
                        latency_ms = int((time.perf_counter() - start_time) * 1000)
                        semantic_cache.set(
                            query=payload.query,
                            query_embedding=query_vector,
                            entry_type="chat",
                            latency_ms=latency_ms,
                            rewritten_query=retrieval_query,
                            was_rewritten=rewrite_result.was_rewritten,
                            answer=accumulated_answer,
                            citations=final_meta.get("citations", []),
                            confidence_score=final_meta.get("confidence_score", 0.8),
                            sufficient_context=final_meta.get("sufficient_context", True)
                        )
                except Exception as stream_ex:
                    logger.error(f"Error in streaming generation: {str(stream_ex)}")
                    yield f"data: {json.dumps({'type': 'content', 'delta': ' [Stream Generation Interrupted]'})}\n\n"
                    
            return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
        else:
            # Sync answer generation with automatic failover
            rag_output = None
            try:
                rag_output = await groq_service.generate_grounded_answer(
                    payload.query, context_chunks, history=history_dicts
                )
            except Exception as groq_err:
                logger.warning(f"Groq generation failed: {str(groq_err)}. Failing over to Gemini...")
                if gemini_service and gemini_service.api_key:
                    rag_output = await gemini_service.generate_grounded_answer(
                        payload.query, context_chunks, history=history_dicts
                    )
                else:
                    raise groq_err
            
            validated_cits = _validate_citations(rag_output.get("citations", []), context_chunks)
            meta_citations = [
                CitationMeta(
                    id=item["id"],
                    source=item["source"],
                    page=item["page"],
                    chunk=item["chunk"],
                    matched_text=item["matched_text"]
                )
                for item in validated_cits
            ]
            
            total_latency = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"Completions query generated in {total_latency}ms.")

            # Store result in cache
            if any(val != 0.0 for val in query_vector):
                semantic_cache.set(
                    query=payload.query,
                    query_embedding=query_vector,
                    entry_type="chat",
                    latency_ms=total_latency,
                    rewritten_query=retrieval_query,
                    was_rewritten=rewrite_result.was_rewritten,
                    answer=rag_output.get("answer", ""),
                    citations=[c.model_dump() for c in meta_citations],
                    confidence_score=float(rag_output.get("confidence_score", 0.8)),
                    sufficient_context=bool(rag_output.get("sufficient_context", True))
                )

            return ChatResponse(
                success=True,
                answer=rag_output.get("answer", ""),
                citations=meta_citations,
                confidence_score=float(rag_output.get("confidence_score", 0.8)),
                sufficient_context=bool(rag_output.get("sufficient_context", True)),
                latency_ms=total_latency,
                original_query=payload.query,
                rewritten_query=rewrite_result.rewritten_query if rewrite_result.was_rewritten else None,
                was_rewritten=rewrite_result.was_rewritten,
                rewrite_latency_ms=rewrite_result.latency_ms,
                cache_hit=False,
                cache_stats=CacheStatsResponse(**semantic_cache.get_stats()),
            )

    except Exception as e:
        logger.error(f"Fatal error compiling completions answer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Grounded generation pipeline failed: {str(e)}"
        )

