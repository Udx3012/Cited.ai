from abc import ABC, abstractmethod
from typing import List, Dict, Any
import httpx
import time
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseReranker(ABC):
    @abstractmethod
    def rerank_chunks(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes a query and a list of chunks, calculates cross-encoder relevance scores,
        attaches them as 'rerank_score', and returns them.
        """
        pass

class HuggingFaceReranker(BaseReranker):
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"
        self.headers = {"Authorization": f"Bearer {settings.HF_API_KEY}"} if settings.HF_API_KEY else {}

    def rerank_chunks(self, query: str, chunks: List[Dict[str, Any]], max_retries: int = 5) -> List[Dict[str, Any]]:
        """
        Queries Hugging Face Serverless Inference for Cross-Encoder scoring.
        Applies exponential backoff retries on rate limits (429) or model loading (503).
        """
        if not chunks:
            return []

        if not settings.HF_API_KEY:
            logger.warning("HF_API_KEY is unconfigured. Returning chunks with mock Reranker scores (1.0).")
            for chunk in chunks:
                chunk["rerank_score"] = 1.0
            return chunks

        # Extract text snippets to rank against the query
        sentences = [c["text"] for c in chunks]
        
        payload = {
            "inputs": {
                "source_sentence": query,
                "sentences": sentences
            }
        }

        logger.info(f"Requesting rerank scores from HF Inference API for {len(chunks)} chunks...")
        
        for attempt in range(max_retries):
            try:
                with httpx.Client() as client:
                    response = client.post(
                        self.api_url, 
                        json=payload, 
                        headers=self.headers, 
                        timeout=60.0
                    )
                
                if response.status_code == 200:
                    data = response.json()
                    scores = self._parse_rerank_scores(data, len(chunks))
                    
                    # Attach scores to chunk records
                    for chunk, score in zip(chunks, scores):
                        chunk["rerank_score"] = score
                    
                    # Sort chunks descending by rerank score
                    chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
                    logger.info("Successfully reranked chunks using BAAI/bge-reranker-base.")
                    return chunks
                
                elif response.status_code == 503:
                    delay = 2 ** attempt
                    logger.warning(f"HF reranker model is loading (503). Retrying in {delay}s...")
                    time.sleep(delay)
                
                elif response.status_code == 429:
                    delay = 2 ** attempt + 1
                    logger.warning(f"HF reranker rate limit hit (429). Retrying in {delay}s...")
                    time.sleep(delay)
                    
                else:
                    raise Exception(f"HF API returned error {response.status_code}: {response.text}")
                    
            except Exception as e:
                logger.error(f"Error calling Hugging Face reranker: {str(e)}")
                if attempt == max_retries - 1:
                    logger.warning("Falling back to pre-existing fusion scores due to HF rerank failure.")
                    # Fallback: preserve original order
                    return chunks
                delay = 2 ** attempt
                time.sleep(delay)
                
        # Safe fallback in case of loop termination without return
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

# Export default instanced reranker
hf_reranker = HuggingFaceReranker()
