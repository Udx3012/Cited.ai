import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ReciprocalRankFusion:
    @staticmethod
    def fuse_results(
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        k: int = 60,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Combines dense vector candidates and sparse keyword candidates 
        into a single ranked sequence using Reciprocal Rank Fusion (RRF).
        """
        logger.info(f"Running Reciprocal Rank Fusion (RRF) on dense={len(dense_results)} and sparse={len(sparse_results)} results (k={k}, limit={limit})")
        
        rrf_scores = {}  # Maps chunk UUID -> RRF score
        chunk_map = {}   # Maps chunk UUID -> Chunk structure
        
        # 1. Score dense candidates
        for idx, chunk in enumerate(dense_results):
            chunk_id = str(chunk["id"])
            chunk_map[chunk_id] = chunk
            
            rank = idx + 1
            rrf_scores[chunk_id] = 1.0 / (k + rank)
            
        # 2. Score sparse candidates
        for idx, chunk in enumerate(sparse_results):
            chunk_id = str(chunk["id"])
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk
            else:
                # Merge sparse bm25_score into pre-existing dense chunk structure
                chunk_map[chunk_id]["bm25_score"] = float(chunk.get("bm25_score", 0.0))
                
            rank = idx + 1
            current_score = rrf_scores.get(chunk_id, 0.0)
            rrf_scores[chunk_id] = current_score + (1.0 / (k + rank))
            
        # 3. Sort candidates descending by RRF score
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        fused_results = []
        for chunk_id in sorted_chunk_ids[:limit]:
            chunk = chunk_map[chunk_id]
            
            fused_chunk = {
                "id": chunk_id,
                "document_name": chunk["metadata"]["document_name"],
                "page": chunk["page_number"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "vector_score": float(chunk.get("vector_score", 0.0)),
                "bm25_score": float(chunk.get("bm25_score", 0.0)),
                "rerank_score": float(rrf_scores[chunk_id])  # Place the fused RRF score in rerank_score
            }
            fused_results.append(fused_chunk)
            
        logger.info(f"Fusing completed. Returning top {len(fused_results)} results.")
        return fused_results
