from fastapi import APIRouter, HTTPException
import time
import logging
from typing import List
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse, ChunkMatch
from app.embeddings.embedder import hf_embedder
from app.services.qdrant import qdrant_service
from app.retrieval.bm25 import bm25_service
from app.retrieval.fusion import ReciprocalRankFusion

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/search", response_model=RetrievalResponse)
async def query_hybrid_retrieval(payload: RetrievalRequest):
    """
    Executes the hybrid RAG retrieval pipeline: dense vector similarity 
    (Qdrant) + sparse lexical weights (BM25) + RRF fusion.
    """
    start_time = time.perf_counter()
    logger.info(f"Received hybrid retrieval query: '{payload.query}' (limit={payload.limit}, top_k={payload.top_k})")
    
    try:
        # Step 1: Dense Vector Retrieval (Qdrant Cloud)
        dense_results = []
        if qdrant_service.client:
            try:
                # Vectorize the search query using HuggingFace bge-large-en-v1.5
                query_vectors = await hf_embedder.embed_documents([payload.query])
                if query_vectors:
                    query_vector = query_vectors[0]
                    
                    # Search Qdrant cosine index
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
            sparse_results = bm25_service.retrieve_sparse(payload.query, top_n=payload.top_k)
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
        
        return RetrievalResponse(
            success=True,
            query=payload.query,
            results=matches,
            latency_ms=latency_ms
        )
        
    except Exception as e:
        logger.error(f"Fatal error executing hybrid RAG retrieval: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal retrieval engine execution error: {str(e)}"
        )
