import re
import threading
import logging
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from app.services.qdrant import qdrant_service

logger = logging.getLogger(__name__)

class BM25Service:
    def __init__(self):
        self.index = None
        self.chunks: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenizes document chunks by lowercasing and splitting on word boundaries.
        """
        return re.findall(r"\b\w+\b", text.lower())

    def rebuild_index(self) -> None:
        """
        Loads all chunks from Qdrant Cloud and builds the in-memory BM25 index.
        Thread-safe to prevent race conditions during parallel ingestion tasks.
        """
        if not qdrant_service.client:
            logger.warning("Qdrant client is not initialized. Skipping BM25 index rebuild.")
            return

        with self.lock:
            try:
                logger.info("Initializing in-memory BM25 index rebuild from Qdrant...")
                all_chunks = []
                offset = None
                
                # Page/scroll through Qdrant collection to collect all points
                while True:
                    response, next_offset = qdrant_service.client.scroll(
                        collection_name=qdrant_service.collection_name,
                        limit=100,
                        with_payload=True,
                        with_vectors=False,
                        offset=offset
                    )
                    
                    for point in response:
                        payload = point.payload
                        if payload:
                            all_chunks.append({
                                "id": point.id,
                                "document_id": payload.get("document_id"),
                                "chunk_index": payload.get("chunk_index"),
                                "page_number": payload.get("page_number"),
                                "text": payload.get("text", ""),
                                "metadata": {
                                    "document_name": payload.get("document_name"),
                                    "page": payload.get("page_number"),
                                    "heading": payload.get("heading"),
                                    "is_ocr": payload.get("is_ocr", False)
                                }
                            })
                            
                    offset = next_offset
                    if offset is None:
                        break
                
                self.chunks = all_chunks
                
                # Construct BM25 index
                if self.chunks:
                    tokenized_corpus = [self._tokenize(c["text"]) for c in self.chunks]
                    self.index = BM25Okapi(tokenized_corpus)
                    logger.info(f"In-memory BM25 index built successfully with {len(self.chunks)} total chunks.")
                else:
                    self.index = None
                    logger.info("BM25 index cleared (zero chunks retrieved).")
                    
            except Exception as e:
                logger.error(f"Failed to rebuild BM25 index: {str(e)}")

    def retrieve_sparse(self, query: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Executes sparse keyword matching on the in-memory BM25 index.
        Returns document chunks ranked by their BM25 score.
        The lock is held only briefly to snapshot the index/chunks references,
        so a concurrent rebuild doesn't block scoring (and vice versa).
        """
        # Snapshot references under lock — don't hold the lock for scoring
        with self.lock:
            index_snapshot  = self.index
            chunks_snapshot = self.chunks

        if not index_snapshot or not chunks_snapshot:
            logger.debug("BM25 index is empty. Returning 0 matching candidates.")
            return []

        tokenized_query = self._tokenize(query)
        scores = index_snapshot.get_scores(tokenized_query)

        results = []
        for idx, score in enumerate(scores):
            # Return points with non-zero relevance scores
            if score > 0.0:
                results.append((score, chunks_snapshot[idx]))

        # Sort descending by score
        results.sort(key=lambda x: x[0], reverse=True)

        sparse_matches = []
        for score, chunk in results[:top_n]:
            matched_chunk = chunk.copy()
            matched_chunk["bm25_score"] = float(score)
            sparse_matches.append(matched_chunk)

        return sparse_matches

# Export default instanced service
bm25_service = BM25Service()
