from fastapi import APIRouter, HTTPException
import time
import logging
from typing import List
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse, ChunkMatch, CacheStatsResponse
from app.embeddings.embedder import hf_embedder
from app.services.qdrant import qdrant_service
from app.retrieval.bm25 import bm25_service
from app.retrieval.fusion import ReciprocalRankFusion
from app.services.query_rewriter import query_rewriter
from app.services.semantic_cache import semantic_cache

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/search", response_model=RetrievalResponse)
async def query_hybrid_retrieval(payload: RetrievalRequest):
    """
    Executes the hybrid RAG retrieval pipeline:
    Query Rewriting → Semantic Cache check → Dense vector similarity (Qdrant) + Sparse lexical (BM25) + RRF fusion.
    """
    start_time = time.perf_counter()
    logger.info(f"Received hybrid retrieval query: '{payload.query}' (limit={payload.limit}, top_k={payload.top_k})")
    
    try:
        # --- Step 0: Intelligent Query Rewriting ---
        # Rewrites ambiguous / conversational queries into retrieval-optimized forms.
        # Falls back to the original query on any error or when rewriting is not needed.
        rewrite_result = await query_rewriter.rewrite(payload.query)
        retrieval_query = rewrite_result.rewritten_query  # used for all downstream lookups
        logger.info(
            f"Query rewriter: was_rewritten={rewrite_result.was_rewritten}, "
            f"retrieval_query='{retrieval_query}', latency={rewrite_result.latency_ms}ms"
        )

        # Generate embedding vector for the query (always needed for cache comparison & dense retrieval)
        query_vector = [0.0] * 1024
        try:
            query_vectors = await hf_embedder.embed_documents([retrieval_query])
            if query_vectors:
                query_vector = query_vectors[0]
        except Exception as embed_ex:
            logger.error(f"Failed to generate query embedding: {str(embed_ex)}")
            # If embedding fails, we proceed without Qdrant and bypass cache (since we need query_vector to check cache)

        # --- Step 0.5: Semantic Cache Lookup ---
        cache_match = None
        if query_vector and any(val != 0.0 for val in query_vector):
            cache_match = semantic_cache.get(retrieval_query, query_vector, entry_type="search")

        if cache_match:
            # Cache Hit path
            cached_results = cache_match.results or []
            matches = [ChunkMatch(**item) for item in cached_results]
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"SemanticCache: HIT for query='{payload.query}' served in {latency_ms}ms with {len(matches)} matches.")
            
            return RetrievalResponse(
                success=True,
                query=payload.query,
                rewritten_query=cache_match.rewritten_query if cache_match.was_rewritten else None,
                was_rewritten=cache_match.was_rewritten,
                results=matches,
                latency_ms=latency_ms,
                rewrite_latency_ms=rewrite_result.latency_ms,
                cache_hit=True,
                cache_stats=CacheStatsResponse(**semantic_cache.get_stats()),
            )

        # --- Cache Miss path: Execute full pipeline ---
        # Step 1: Dense Vector Retrieval (Qdrant Cloud)
        dense_results = []
        if qdrant_service.client and any(val != 0.0 for val in query_vector):
            try:
                # Search Qdrant cosine index using the query_vector we already generated
                search_results = qdrant_service.client.search(
                    collection_name=qdrant_service.collection_name,
                    query_vector=query_vector,
                    limit=payload.top_k,
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
            except Exception as vector_ex:
                logger.error(f"Dense vector retrieval failed: {str(vector_ex)}")
                # Continue with sparse-only matching if dense retrieval errors out
        
        # Step 2: Sparse Lexical Retrieval (In-Memory BM25)
        sparse_results = []
        try:
            sparse_results = bm25_service.retrieve_sparse(retrieval_query, top_n=payload.top_k)
        except Exception as sparse_ex:
            logger.error(f"Sparse lexical search failed: {str(sparse_ex)}")

        # Step 3: Reciprocal Rank Fusion (RRF)
        fused_results = ReciprocalRankFusion.fuse_results(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=payload.rrf_k,
            limit=payload.limit
        )
        
        # Map output schemas
        matches = [ChunkMatch(**item) for item in fused_results]
        
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"Hybrid retrieval search completed in {latency_ms}ms with {len(matches)} matches.")
        
        # Store result in cache
        if any(val != 0.0 for val in query_vector):
            semantic_cache.set(
                query=payload.query,
                query_embedding=query_vector,
                entry_type="search",
                latency_ms=latency_ms,
                rewritten_query=retrieval_query,
                was_rewritten=rewrite_result.was_rewritten,
                results=[item.model_dump() for item in matches]
            )

        return RetrievalResponse(
            success=True,
            query=payload.query,
            rewritten_query=rewrite_result.rewritten_query if rewrite_result.was_rewritten else None,
            was_rewritten=rewrite_result.was_rewritten,
            results=matches,
            latency_ms=latency_ms,
            rewrite_latency_ms=rewrite_result.latency_ms,
            cache_hit=False,
            cache_stats=CacheStatsResponse(**semantic_cache.get_stats()),
        )
        
    except Exception as e:
        logger.error(f"Fatal error executing hybrid RAG retrieval: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal retrieval engine execution error: {str(e)}"
        )
