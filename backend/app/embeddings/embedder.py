from abc import ABC, abstractmethod
from typing import List, Any
import asyncio
import httpx
import time
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseEmbedder(ABC):
    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generates dense vector embeddings for a list of text strings.
        Returns a list of float arrays representing the vector space.
        """
        pass

class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5"):
        self.model_name = model_name
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{self.model_name}"
        self.headers = {"Authorization": f"Bearer {settings.HF_API_KEY}"} if settings.HF_API_KEY else {}
        self.client = httpx.Client()

    async def embed_documents(self, texts: List[str], max_retries: int = 5) -> List[List[float]]:
        """
        Retrieves embeddings via Hugging Face Serverless Inference.
        Applies exponential backoff retries for 503 (model loading) or 429 (rate limits).
        Runs in a thread pool executor to avoid blocking FastAPI's async event loop.
        """
        if not settings.HF_API_KEY:
            logger.warning("HF_API_KEY is unconfigured. Returning mock zero-vectors (1024 dimensions).")
            return [[0.0] * 1024 for _ in texts]

        payload = {
            "inputs": texts,
            "options": {"wait_for_model": True}
        }

        loop = asyncio.get_event_loop()

        def _sync_embed(attempt: int) -> Any:
            logger.info(f"Requesting embeddings from HF Inference API for {len(texts)} texts (Attempt {attempt + 1}/{max_retries})...")
            return self.client.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=15.0  # Fail fast — cold HF model loads > 15s should retry
            )

        for attempt in range(max_retries):
            try:
                response = await loop.run_in_executor(None, _sync_embed, attempt)

                if response.status_code == 200:
                    data = response.json()
                    return self._process_embeddings_response(data)

                elif response.status_code == 503:
                    delay = 2 ** attempt
                    logger.warning(f"Hugging Face model is loading (503). Retrying in {delay}s...")
                    await asyncio.sleep(delay)

                elif response.status_code == 429:
                    delay = 2 ** attempt + 1
                    logger.warning(f"Hugging Face rate limit hit (429). Retrying in {delay}s...")
                    await asyncio.sleep(delay)

                else:
                    raise Exception(f"Hugging Face API returned error {response.status_code}: {response.text}")

            except Exception as e:
                logger.error(f"Error calling Hugging Face embeddings: {str(e)}")
                if attempt == max_retries - 1:
                    raise Exception(f"Failed to generate embeddings after {max_retries} attempts: {str(e)}")
                delay = 2 ** attempt
                await asyncio.sleep(delay)

        raise Exception("Failed to retrieve vector embeddings (Max retries reached).")

    def _process_embeddings_response(self, data: Any) -> List[List[float]]:
        """
        Parses Hugging Face API responses. If it returns token-level 3D vectors
        [batch_size, sequence_length, vector_dim], we perform mean pooling.
        """
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"Unexpected response format from Hugging Face: {type(data)}")

        # Check if 3D array (token-level embeddings)
        if isinstance(data[0], list) and len(data[0]) > 0:
            if isinstance(data[0][0], list):
                logger.info("HF returned token-level 3D embeddings. Performing mean-pooling over sequence...")
                pooled_embeddings = []
                for doc in data:
                    num_tokens = len(doc)
                    vector_dim = len(doc[0])
                    mean_vector = [0.0] * vector_dim
                    for token_vec in doc:
                        for idx in range(vector_dim):
                            mean_vector[idx] += token_vec[idx]
                    mean_vector = [val / num_tokens for val in mean_vector]
                    pooled_embeddings.append(mean_vector)
                return pooled_embeddings

        # If already 2D array, return directly
        return data

class VoyageEmbedder(BaseEmbedder):
    def __init__(self, model_name: str = "voyage-3"):
        self.model_name = model_name
        self.api_url = "https://api.voyageai.com/v1/embeddings"
        self.client = httpx.Client()

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Retrieves vector embeddings using Voyage AI's API.
        """
        if not settings.VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY is unconfigured.")

        payload = {
            "input": texts,
            "model": self.model_name
        }
        headers = {
            "Authorization": f"Bearer {settings.VOYAGE_API_KEY}",
            "Content-Type": "application/json"
        }

        loop = asyncio.get_event_loop()

        def _sync_voyage() -> Any:
            logger.info(f"Requesting embeddings from Voyage API for {len(texts)} texts...")
            return self.client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=12.0
            )

        response = await loop.run_in_executor(None, _sync_voyage)
        if response.status_code == 200:
            res_data = response.json()
            # Voyage response contains list of { "embedding": [...], "index": 0 }
            embeddings = [item["embedding"] for item in res_data["data"]]
            return embeddings
        else:
            raise Exception(f"Voyage API returned status code {response.status_code}: {response.text}")

class GroundedEmbedder(BaseEmbedder):
    def __init__(self):
        self.voyage = VoyageEmbedder()
        self.hf = HuggingFaceEmbedder()

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Retrieves vector embeddings trying Voyage AI first, and falling back
        seamlessly to Hugging Face if Voyage fails or is unconfigured.
        """
        if settings.VOYAGE_API_KEY:
            try:
                return await self.voyage.embed_documents(texts)
            except Exception as e:
                logger.warning(f"Voyage AI embedding generation failed, falling back to Hugging Face: {str(e)}")
        
        # Fall back to Hugging Face Serverless API
        return await self.hf.embed_documents(texts)

# Export default instanced embedder
hf_embedder = GroundedEmbedder()
