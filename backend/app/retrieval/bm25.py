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

    def _tokenize(self, text: str, filter_stopwords: bool = False) -> List[str]:
        """
        Tokenizes document chunks by lowercasing and splitting on word boundaries.
        Filters conversational noise when filter_stopwords is True.
        """
        tokens = re.findall(r"\b\w+\b", text.lower())
        if filter_stopwords:
            stopwords = {
                "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", 
                "of", "with", "by", "from", "as", "is", "are", "was", "were", "be", 
                "been", "being", "have", "has", "had", "do", "does", "did", "can", 
                "could", "should", "would", "will", "shall", "may", "might", "must",
                "explain", "detail", "detailed", "describe", "tell", "about", "give", 
                "show", "what", "which", "who", "whom", "this", "that", "these", "those"
            }
            substantive = [t for t in tokens if t not in stopwords and len(t) > 1]
            return substantive if substantive else tokens
        return tokens

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
                            doc_name = (
                                payload.get("document_name")
                                or payload.get("metadata", {}).get("document_name")
                                or "unknown"
                            )
                            all_chunks.append({
                                "id": point.id,
                                "document_id": payload.get("document_id"),
                                "document_name": doc_name,
                                "chunk_index": payload.get("chunk_index"),
                                "page_number": payload.get("page_number", 1),
                                "text": payload.get("text", ""),
                                "metadata": {
                                    "document_name": doc_name,
                                    "page": payload.get("page_number", 1),
                                    "heading": payload.get("heading", "Introduction"),
                                    "is_ocr": payload.get("is_ocr", False)
                                }
                            })
                            
                    offset = next_offset
                    if offset is None:
                        break
                
                self.chunks = all_chunks
                
                # Construct BM25 index indexing document_name, heading, and text
                if self.chunks:
                    tokenized_corpus = [
                        self._tokenize(
                            f"{c.get('document_name', '')} "
                            f"{c.get('metadata', {}).get('heading', '')} "
                            f"{c.get('text', '')}"
                        )
                        for c in self.chunks
                    ]
                    self.index = BM25Okapi(tokenized_corpus)
                    logger.info(f"In-memory BM25 index built successfully with {len(self.chunks)} total chunks.")
                else:
                    self.index = None
                    logger.info("BM25 index cleared (zero chunks retrieved).")
                    
            except Exception as e:
                logger.error(f"Failed to rebuild BM25 index: {str(e)}")

    def get_uploaded_documents(self) -> List[Dict[str, Any]]:
        """
        Returns structured inventory of all unique uploaded documents.
        """
        with self.lock:
            docs = {}
            for c in self.chunks:
                name = c.get("document_name") or c.get("metadata", {}).get("document_name")
                if not name or name == "System Metadata":
                    continue
                if name not in docs:
                    docs[name] = {"document_name": name, "chunk_count": 0, "pages": set()}
                docs[name]["chunk_count"] += 1
                page = c.get("page_number") or c.get("page") or c.get("metadata", {}).get("page", 1)
                docs[name]["pages"].add(page)
            return [
                {
                    "document_name": name,
                    "chunk_count": data["chunk_count"],
                    "page_count": len(data["pages"])
                }
                for name, data in sorted(docs.items())
            ]

    def get_chunks_for_document(self, doc_name: str, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Retrieves top chunks belonging to a specific document name.
        """
        with self.lock:
            matched = []
            target = doc_name.lower().strip()
            for c in self.chunks:
                c_name = (c.get("document_name") or c.get("metadata", {}).get("document_name", "")).lower()
                if target in c_name or c_name in target:
                    matched_chunk = c.copy()
                    matched_chunk["bm25_score"] = 2.5
                    matched_chunk["vector_score"] = 0.9
                    matched_chunk["rerank_score"] = 0.95
                    matched_chunk["reranker_applied"] = True
                    matched.append(matched_chunk)
                    if len(matched) >= limit:
                        break
            return matched

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

        tokenized_query = self._tokenize(query, filter_stopwords=True)
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
            matched_chunk["document_name"] = chunk.get("document_name") or chunk.get("metadata", {}).get("document_name", "unknown")
            sparse_matches.append(matched_chunk)

        return sparse_matches

# Export default instanced service
bm25_service = BM25Service()
