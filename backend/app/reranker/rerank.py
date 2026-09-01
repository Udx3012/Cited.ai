from abc import ABC, abstractmethod
from typing import List, Dict, Any
import asyncio
import httpx
import time
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseReranker(ABC):
    @abstractmethod
    async def rerank_chunks(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes a query and a list of chunks, calculates cross-encoder relevance scores,
        attaches them as 'rerank_score', and returns them.
        """
        pass

class HuggingFaceReranker(BaseReranker):
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{self.model_name}"
        self.headers = {"Authorization": f"Bearer {settings.HF_API_KEY}"} if settings.HF_API_KEY else {}
        self.client = httpx.AsyncClient()

    async def rerank_chunks(self, query: str, chunks: List[Dict[str, Any]], max_retries: int = 1) -> List[Dict[str, Any]]:
        """
        Queries Hugging Face Serverless Inference for Cross-Encoder scoring.
        Applies fast fallback on rate limits (429) or model loading (503) to prevent UI lag.
        """
        if not chunks:
            return []

        if not settings.HF_API_KEY:
            logger.warning("HF_API_KEY is unconfigured. Preserving pre-existing chunk rankings.")
            for chunk in chunks:
                if "rerank_score" not in chunk:
                    chunk["rerank_score"] = float(chunk.get("vector_score", 1.0))
            return chunks

        # Extract text snippets to rank against the query
        sentences = [c.get("text", "") for c in chunks]

        payload = {
            "inputs": {
                "source_sentence": query,
                "sentences": sentences
            }
        }

        logger.info(f"Requesting rerank scores from HF Inference API for {len(chunks)} chunks...")

        for attempt in range(max_retries + 1):
            try:
                response = await self.client.post(
                    self.api_url,
                    json=payload,
                    headers=self.headers,
                    timeout=2.0  # Fast SLA ceiling
                )

                if response.status_code == 200:
                    data = response.json()
                    scores = self._parse_rerank_scores(data, len(chunks))

                    # Attach scores to chunk records
                    for chunk, score in zip(chunks, scores):
                        chunk["rerank_score"] = score

                    # Sort chunks descending by rerank score
                    chunks.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
                    logger.info("Successfully reranked chunks using BAAI/bge-reranker-base.")
                    return chunks

                elif response.status_code in (503, 429) and attempt < max_retries:
                    logger.warning(f"HF reranker returned {response.status_code}. Retrying once...")
                    await asyncio.sleep(0.5)
                else:
                    logger.warning(f"HF API returned status {response.status_code}. Falling back to fusion scores.")
                    break

            except Exception as e:
                logger.warning(f"Cross-encoder reranking exception: {str(e)}. Falling back to fusion scores.")
                break

        # Safe fallback: ensure all chunks have a numeric rerank_score
        for chunk in chunks:
            if "rerank_score" not in chunk:
                chunk["rerank_score"] = float(chunk.get("vector_score", 0.0))
        return chunks

    def _parse_rerank_scores(self, data: Any, expected_count: int) -> List[float]:
        """
        Parses classification/reranker outputs of different shapes, returning a list of float scores.
        """
        scores = []
        
        # If response is a flat list of scores
        if isinstance(data, list):
            for item in data:
                if isinstance(item, (int, float)):
                    scores.append(float(item))
                elif isinstance(item, dict):
                    # E.g. {"label": "LABEL_0", "score": 0.85}
                    scores.append(float(item.get("score", 0.0)))
                elif isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict):
                    # E.g. [{"label": "score", "score": 0.85}]
                    scores.append(float(item[0].get("score", 0.0)))
                else:
                    scores.append(0.0)
                    
        # Pad with 0.0 if the count does not match the expectations
        while len(scores) < expected_count:
            scores.append(0.0)
            
        return scores[:expected_count]

class VoyageReranker(BaseReranker):
    def __init__(self, model_name: str = "rerank-2"):
        self.model_name = model_name
        self.api_url = "https://api.voyageai.com/v1/rerank"
        self.client = httpx.AsyncClient()


    async def rerank_chunks(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Queries Voyage AI for high-performance reranking scores.
        """
        if not chunks:
            return []

        if not settings.VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY is unconfigured.")

        sentences = [c.get("text", "") for c in chunks]
        payload = {
            "query": query,
            "documents": sentences,
            "model": self.model_name
        }
        headers = {
            "Authorization": f"Bearer {settings.VOYAGE_API_KEY}",
            "Content-Type": "application/json"
        }

        logger.info(f"Requesting rerank from Voyage API for {len(chunks)} chunks...")
        response = await self.client.post(
            self.api_url,
            json=payload,
            headers=headers,
            timeout=3.0
        )
        if response.status_code == 200:
            res_data = response.json()
            results = res_data.get("data", [])
            
            # Map scores back to original chunks using index mapping
            for item in results:
                idx = item.get("index")
                if idx is not None and 0 <= idx < len(chunks):
                    chunks[idx]["rerank_score"] = float(item.get("relevance_score", 0.0))

            # Default un-ranked chunks to 0.0 rerank score
            for c in chunks:
                if "rerank_score" not in c:
                    c["rerank_score"] = float(c.get("vector_score", 0.0))

            # Sort descending by score
            chunks.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
            logger.info("Successfully reranked chunks using Voyage reranker.")
            return chunks
        else:
            raise Exception(f"Voyage rerank API returned status code {response.status_code}: {response.text}")

class GroundedReranker(BaseReranker):
    def __init__(self):
        self.voyage = VoyageReranker()
        self.hf = HuggingFaceReranker()

    async def rerank_chunks(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Dynamically dispatches queries to Voyage Rerank API first, 
        and falls back to Hugging Face cross-encoder if it fails or is unconfigured.
        """
        if settings.VOYAGE_API_KEY:
            try:
                return await self.voyage.rerank_chunks(query, chunks)
            except Exception as e:
                logger.warning(f"Voyage Reranker failed, falling back to Hugging Face: {str(e)}")
        
        # Fall back to Hugging Face Serverless API
        return await self.hf.rerank_chunks(query, chunks)

# Export default instanced reranker
hf_reranker = GroundedReranker()

