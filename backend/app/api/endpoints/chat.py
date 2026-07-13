from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
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
        # --- Step 1: Dense Retrieval (Qdrant Cloud) ---
        dense_results = []
        if qdrant_service.client:
            try:
                # Vectorize search query (dimension: 1024)
                query_vectors = hf_embedder.embed_documents([payload.query])
                if query_vectors:
                    query_vector = query_vectors[0]
                    search_results = qdrant_service.client.search(
                        collection_name=qdrant_service.collection_name,
                        query_vector=query_vector,
                        limit=20,  # Fetch top 20 for fusion
                        with_payload=True
                    )
                    
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

        # --- Step 2: Sparse Retrieval (BM25) ---
        sparse_results = []
        try:
            sparse_results = bm25_service.retrieve_sparse(payload.query, top_n=20)
        except Exception as e:
            logger.error(f"Sparse lexical search failed: {str(e)}")

        # --- Step 3: Reciprocal Rank Fusion (RRF) ---
        fused_chunks = ReciprocalRankFusion.fuse_results(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=60,
            limit=15  # Pass top 15 fused candidates to the reranker
        )

        # --- Step 4: Cross-Encoder Reranking (bge-reranker-base) ---
        reranked_chunks = []
        try:
            reranked_chunks = hf_reranker.rerank_chunks(payload.query, fused_chunks)
        except Exception as e:
            logger.error(f"Cross-encoder reranking failed: {str(e)}")
            reranked_chunks = fused_chunks  # Fallback to fusion ranking order

        # Truncate context to top 5 chunks for LLM context size and prompt efficiency
        context_chunks = reranked_chunks[:5]

        # 2. AI Guardrail: Confidence-based response filtering
        # Check if the query is a general greeting or chit-chat first
        def is_general_chat(query_text: str) -> bool:
            q = query_text.strip().lower().rstrip("?.-!")
            greetings = {"hi", "hello", "hey", "hola", "greetings", "good morning", "good afternoon", "good evening", "howdy", "yo", "sup", "hi there", "hello there", "what's up", "whats up"}
            farewells = {"bye", "goodbye", "see you", "farewell", "cya"}
            gratitude = {"thanks", "thank you", "thank you so much", "perfect thanks", "ok thanks", "great thanks"}
            chitchat = {"how are you", "how's it going", "hows it going", "how are you doing", "what's new", "whats new"}
            identity = {"who are you", "what is your name", "tell me about yourself", "what do you do", "what are you", "who created you", "who made you", "what is cited.ai", "what is cited"}
            
            if q in greetings or q in farewells or q in gratitude or q in chitchat or q in identity:
                return True
            
            if len(q.split()) <= 2:
                words = set(q.split())
                if words.intersection(greetings) or words.intersection(farewells) or words.intersection(gratitude):
                    return True
            return False

        # If no chunks match, or if the top candidate has vector similarity < 0.65
        insufficient_context = False
        if not is_general_chat(payload.query):
            if not context_chunks:
                insufficient_context = True
            else:
                top_chunk = context_chunks[0]
                if top_chunk.get("vector_score", 0.0) < 0.65 and top_chunk.get("bm25_score", 0.0) == 0.0:
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
                                        "page": chunk.get("page_number", 1),
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
                            page=chunk.get("page_number", 1),
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
