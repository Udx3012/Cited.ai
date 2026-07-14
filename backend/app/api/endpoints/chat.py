from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import asyncio
import time
import json
import logging
from typing import List, Dict, Any
from app.schemas.chat import ChatRequest, ChatResponse, CitationMeta
from app.embeddings.embedder import hf_embedder
from app.services.qdrant import qdrant_service
from app.retrieval.bm25 import bm25_service
from app.retrieval.fusion import ReciprocalRankFusion
from app.reranker.rerank import hf_reranker
from app.services.groq import groq_service

logger = logging.getLogger(__name__)
router = APIRouter()

def is_general_chat(query_text: str) -> bool:
    """
    Returns True if the query is a greeting, farewell, gratitude, chit-chat,
    identity question, or app-meta question that does not require document retrieval.

    Handles:
    - Exact match greetings / farewells / gratitude ("hello", "thanks")
    - Short (<=2 word) queries containing greeting tokens ("hey there")
    - Greeting-prefixed questions ("hey, can i upload a doc?")
    - App-capability / meta questions ("how do i upload?", "can i add a pdf?")
    """
    import re
    q = query_text.strip().lower()
    q_stripped = q.rstrip("?.-!")

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

    # 2. Short query (<=2 words) containing a greeting/farewell/gratitude token
    words = q_stripped.split()
    if len(words) <= 2:
        word_set = set(words)
        if word_set & greeting_tokens or word_set & farewell_tokens or word_set & gratitude_tokens:
            return True

    # 3. Greeting-prefixed question: starts with a greeting word, then has more content
    #    e.g. "hey, can i upload a doc" / "hello what can you do"
    first_word = words[0].rstrip(",!") if words else ""
    if first_word in greeting_tokens and len(words) > 1:
        return True

    # 4. App-meta / capability questions — about Cited.ai features, not document content
    app_meta_patterns = [
        r"\b(upload|add|attach|import)\b.{0,30}\b(doc|document|pdf|file|paper)\b",
        r"\b(doc|document|pdf|file|paper)\b.{0,30}\b(upload|add|attach|import)\b",
        r"\bhow (do|can|does|should) (i|we|you)\b",
        r"\bcan (i|we|you)\b.{0,20}\b(upload|search|use|ask|chat|query|add|delete|remove)\b",
        r"\bwhat (can|does|do) (you|this|cited(\.ai)?)\b",
        r"\bsupported (file|format|type)\b",
        r"\b(how|what).{0,20}\b(work|feature|function|capability|able to)\b",
    ]
    for pattern in app_meta_patterns:
        if re.search(pattern, q):
            return True

    return False


@router.post("/completions")
async def chat_completions(payload: ChatRequest):
    """
    Submits conversational query to the grounded RAG generator.
    Runs hybrid retrieval (dense + sparse), fuses results via RRF, 
    reranks via cross-encoder, and synthesizes answers via Groq LLM.
    Supports optional Server-Sent Events (SSE) token streaming.
    Includes robust prompt injection detection, citation validators, and confidence-based filters.
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
        logger.warning(f"Guardrail Check: Prompt injection/leakage keyword matched in query: '{payload.query}'")
        if payload.stream:
            async def sse_injection_refusal():
                yield f"data: {json.dumps({'type': 'content', 'delta': 'I cannot answer this question due to safety policy guidelines.'})}\n\n"
                yield f"data: {json.dumps({'type': 'metadata', 'citations': [], 'confidence_score': 0.0, 'sufficient_context': False})}\n\n"
            return StreamingResponse(sse_injection_refusal(), media_type="text/event-stream")
        else:
            return ChatResponse(
                success=False,
                answer="I cannot answer this question due to safety policy guidelines.",
                citations=[],
                confidence_score=0.0,
                sufficient_context=False,
                latency_ms=0
            )

    try:
        # --- Early Exit: General Chat / Greetings ---
        # Skip the entire retrieval pipeline for greetings, chit-chat, and identity queries.
        # These do NOT need embeddings, Qdrant search, BM25, or reranking.
        if is_general_chat(payload.query):
            logger.info("General chat query detected. Skipping retrieval pipeline.")
            context_chunks = []
            if payload.stream:
                async def sse_general_chat_stream():
                    async for event in groq_service.generate_grounded_answer_stream(payload.query, context_chunks):
                        yield f"data: {json.dumps(event)}\n\n"
                return StreamingResponse(sse_general_chat_stream(), media_type="text/event-stream")
            else:
                rag_output = await groq_service.generate_grounded_answer(payload.query, context_chunks)
                total_latency = int((time.perf_counter() - start_time) * 1000)
                logger.info(f"General chat answered in {total_latency}ms.")
                return ChatResponse(
                    success=True,
                    answer=rag_output.get("answer", ""),
                    citations=[],
                    confidence_score=1.0,
                    sufficient_context=True,
                    latency_ms=total_latency
                )

        # --- Step 1: Parallel Embed + BM25 ---
        # Run HF embedding and BM25 concurrently to eliminate sequential wait.
        loop = asyncio.get_event_loop()

        async def _embed_query():
            return await hf_embedder.embed_documents([payload.query])

        async def _bm25_query():
            # BM25 is CPU-bound/in-memory — run in executor to not block the event loop
            return await loop.run_in_executor(
                None, bm25_service.retrieve_sparse, payload.query, 20
            )

        embed_task  = asyncio.ensure_future(_embed_query())
        bm25_task   = asyncio.ensure_future(_bm25_query())

        try:
            query_vectors_list, sparse_results = await asyncio.gather(embed_task, bm25_task)
        except Exception as e:
            logger.error(f"Parallel embed/BM25 failed: {str(e)}")
            query_vectors_list, sparse_results = [], []

        # --- Step 2: Dense Retrieval (Qdrant Cloud) ---
        dense_results = []
        if qdrant_service.client and query_vectors_list:
            try:
                query_vector = query_vectors_list[0]

                # Qdrant .search() is synchronous — run in executor to avoid blocking the event loop
                def _qdrant_search():
                    return qdrant_service.client.search(
                        collection_name=qdrant_service.collection_name,
                        query_vector=query_vector,
                        limit=20,
                        with_payload=True
                    )

                search_results = await loop.run_in_executor(None, _qdrant_search)

                for point in search_results:
                    payload_data = point.payload or {}
                    dense_results.append({
                        "id": point.id,
                        "page_number": payload_data.get("page_number", 1),
                        "chunk_index": payload_data.get("chunk_index", 0),
                        "text": payload_data.get("text", ""),
                        "vector_score": float(point.score),
                        "bm25_score": 0.0,
                        "metadata": {
                            "document_name": payload_data.get("document_name", "unknown"),
                            "page": payload_data.get("page_number", 1),
                            "heading": payload_data.get("heading", "Introduction"),
                            "is_ocr": payload_data.get("is_ocr", False)
                        }
                    })
            except Exception as e:
                logger.error(f"Dense vector search failed: {str(e)}")

        # --- Step 3: Reciprocal Rank Fusion (RRF) ---
        fused_chunks = ReciprocalRankFusion.fuse_results(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=60,
            limit=15  # Pass top 15 fused candidates to the reranker
        )

        # --- Step 4: Cross-Encoder Reranking (bge-reranker-base) ---
        # Skip reranking when there are ≤3 candidates — RRF ordering is already good
        # enough and calling HF Serverless for 3 items is wasteful.
        # Apply an 8-second hard timeout so a cold HF model start doesn't stall the response.
        reranked_chunks = []
        if len(fused_chunks) > 3:
            try:
                reranked_chunks = await asyncio.wait_for(
                    hf_reranker.rerank_chunks(payload.query, fused_chunks),
                    timeout=8.0
                )
            except asyncio.TimeoutError:
                logger.warning("Reranker timed out after 8s — falling back to RRF order.")
                reranked_chunks = fused_chunks
            except Exception as e:
                logger.error(f"Cross-encoder reranking failed: {str(e)}")
                reranked_chunks = fused_chunks  # Fallback to fusion ranking order
        else:
            reranked_chunks = fused_chunks  # ≤3 chunks — skip reranker

        # Truncate context to top 5 chunks for LLM context size and prompt efficiency
        context_chunks = reranked_chunks[:5]

        # 2. AI Guardrail: Confidence-based response filtering
        insufficient_context = False
        if not is_general_chat(payload.query):
            if not context_chunks:
                insufficient_context = True
            else:
                max_vector_score = max(c.get("vector_score", 0.0) for c in context_chunks)
                max_bm25_score   = max(c.get("bm25_score", 0.0) for c in context_chunks)
                max_rerank_score = max(c.get("rerank_score", 0.0) for c in context_chunks)
                has_signal = (
                    max_vector_score >= 0.40
                    or max_bm25_score > 0.0
                    or max_rerank_score > 0.0
                )
                if not has_signal:
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
                    latency_ms=int((time.perf_counter() - start_time) * 1000)
                )

        # --- Step 5: Generation (Groq Llama 3) ---
        if payload.stream:
            # SSE streaming generator yielding token deltas and final metadata
            async def sse_event_generator():
                try:
                    async for event in groq_service.generate_grounded_answer_stream(payload.query, context_chunks):
                        if event.get("type") == "metadata":
                            # AI Guardrail: Validate citation indices in event payload
                            validated_citations = []
                            for c in event.get("citations", []):
                                cit_id = c.get("id")
                                if isinstance(cit_id, int) and 1 <= cit_id <= len(context_chunks):
                                    chunk = context_chunks[cit_id - 1]
                                    validated_citations.append({
                                        "id": cit_id,
                                        "source": chunk.get("document_name", "unknown"),
                                        # fusion.py stores page under key "page", not "page_number"
                                        "page": chunk.get("page", chunk.get("page_number", 1)),
                                        "chunk": chunk.get("chunk_index", 0),
                                        "matched_text": c.get("matched_text") or chunk.get("text", "")[:200],
                                        "vector_score": chunk.get("vector_score", 0.0),
                                        "bm25_score": chunk.get("bm25_score", 0.0),
                                        "rerank_score": chunk.get("rerank_score", 0.0)
                                    })
                            event["citations"] = validated_citations
                        yield f"data: {json.dumps(event)}\n\n"
                except Exception as stream_ex:
                    logger.error(f"Error in streaming generation: {str(stream_ex)}")
                    yield f"data: {json.dumps({'type': 'content', 'delta': ' [Stream Generation Interrupted]'})}\n\n"
                    
            return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
        else:
            # Sync answer generation
            rag_output = await groq_service.generate_grounded_answer(payload.query, context_chunks)
            
            # AI Guardrail: Validate citation indices in RAG response
            meta_citations = []
            for item in rag_output.get("citations", []):
                cit_id = item.get("id")
                if isinstance(cit_id, int) and 1 <= cit_id <= len(context_chunks):
                    chunk = context_chunks[cit_id - 1]
                    meta_citations.append(
                        CitationMeta(
                            id=cit_id,
                            source=chunk.get("document_name", "unknown"),
                            # fusion.py stores page under key "page", not "page_number"
                            page=chunk.get("page", chunk.get("page_number", 1)),
                            chunk=chunk.get("chunk_index", 0),
                            matched_text=item.get("matched_text") or chunk.get("text", "")[:200]
                        )
                    )
            
            total_latency = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"Completions query generated in {total_latency}ms.")

            return ChatResponse(
                success=True,
                answer=rag_output.get("answer", ""),
                citations=meta_citations,
                confidence_score=float(rag_output.get("confidence_score", 0.0)),
                sufficient_context=bool(rag_output.get("sufficient_context", False)),
                latency_ms=total_latency
            )

    except Exception as e:
        logger.error(f"Fatal error compiling completions answer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Grounded generation pipeline failed: {str(e)}"
        )
