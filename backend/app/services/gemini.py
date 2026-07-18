import httpx
import json
import logging
from typing import List, Dict, Any, AsyncGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = "gemini-2.5-flash"
        self.client = httpx.AsyncClient()

    def _build_prompts(self, query: str, context_chunks: List[Dict[str, Any]]) -> tuple:
        """
        Builds the system and user prompts for grounded RAG generation,
        matching the exact formatting expected by the parser.
        """
        system_prompt = (
            "You are a helpful, extremely precise AI search assistant. Answer the user query using the provided document context chunks.\n"
            "Each chunk starts with an index identifier like [Index: N] where N is a number.\n"
            "Ground your answer strictly inside the provided context if the query relates to the documents. Do not make assumptions or extrapolate.\n"
            "Cite documents using their index numbers (e.g., [1], [2]) at the end of sentences that utilize that chunk's information.\n\n"
            "However, if the query is a general greeting, farewell, expression of gratitude, or general conversational chit-chat "
            "(e.g. 'hi', 'hello', 'who are you', 'how are you', 'thank you', etc.) that does not require information from the documents, "
            "respond politely as a general AI assistant. In this case, do not use any citation markers. In the JSON metadata, "
            "set sufficient_context to true, confidence_score to 1.0, and set the citations array to [].\n\n"
            "If the query asks about the documents but the provided document context chunks do not contain enough information, follow these rules:\n"
            "1. State clearly: \"I do not have sufficient information in the provided documents to answer this question.\"\n"
            "2. Do not use any citation markers.\n"
            "3. Set sufficient_context to false, confidence_score to 0.0, and clear the citations array.\n\n"
            "Format your output as follows:\n"
            "Answer the query naturally, incorporating citation markers like [1], [2] at the end of sentences if using context.\n"
            "At the very end of your response, write the delimiter ||METADATA|| followed by a raw JSON object with this exact schema:\n"
            "{\n"
            "  \"citations\": [\n"
            "    {\n"
            "      \"id\": 1,\n"
            "      \"source\": \"Filename.pdf\",\n"
            "      \"page\": 4,\n"
            "      \"chunk\": 12,\n"
            "      \"matched_text\": \"Exact sentence or short text snippet from the context that supports the assertion\"\n"
            "    }\n"
            "  ],\n"
            "  \"confidence_score\": 0.95,\n"
            "  \"sufficient_context\": true\n"
            "}\n"
            "Do not output any other text after the JSON metadata."
        )

        context_str = ""
        for idx, chunk in enumerate(context_chunks):
            context_str += (
                f"[Index: {idx + 1}]\n"
                f"Source Document: {chunk.get('document_name', 'unknown')}\n"
                f"Page: {chunk.get('page', chunk.get('page_number', 1))}\n"
                f"Content: {chunk.get('text', '')}\n"
                "-----------------------------------\n\n"
            )

        user_prompt = (
            f"Provided Document Context Chunks:\n\n{context_str}"
            f"User Query Question: {query}"
        )

        return system_prompt, user_prompt

    async def generate_grounded_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Queries Gemini LLM (non-streaming mode) and returns a structured JSON answer payload.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is unconfigured.")

        system_prompt, user_prompt = self._build_prompts(query, context_chunks)
        
        # Combine system instructions and user prompt in the Gemini contents format
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0
            }
        }

        logger.info(f"Submitting grounded generation request to Gemini ({self.model_name})...")
        response = await self.client.post(api_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30.0)
        
        if response.status_code != 200:
            raise Exception(f"Gemini API returned error {response.status_code}: {response.text}")
        
        result = response.json()
        try:
            raw_text = result["candidates"][0]["content"]["parts"][0].get("text", "")
        except (KeyError, IndexError):
            raise Exception(f"Unexpected response format from Gemini API: {result}")
        
        return self._parse_raw_llm_response(raw_text)

    async def generate_grounded_answer_stream(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams response tokens (SSE) for the answer text, 
        yielding citations and confidence scores as a metadata chunk at the end.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is unconfigured.")

        system_prompt, user_prompt = self._build_prompts(query, context_chunks)
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:streamGenerateContent?key={self.api_key}&alt=sse"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0
            }
        }

        delimiter = "||METADATA||"
        del_len = len(delimiter)
        accum = ""
        in_metadata = False
        metadata_str = ""

        logger.info(f"Submitting streaming completions request to Gemini ({self.model_name})...")
        
        async with self.client.stream("POST", api_url, json=payload, headers={"Content-Type": "application/json"}, timeout=35.0) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                raise Exception(f"Gemini stream request failed: {response.status_code} - {error_body.decode()}")
            
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        chunk_data = json.loads(data_str)
                        delta = chunk_data["candidates"][0]["content"]["parts"][0].get("text", "")
                    except Exception:
                        continue

                    if not in_metadata:
                        accum += delta
                        if delimiter in accum:
                            parts = accum.split(delimiter)
                            if parts[0]:
                                yield {"type": "content", "delta": parts[0]}
                            metadata_str = parts[1]
                            in_metadata = True
                        else:
                            if len(accum) > del_len:
                                yield {"type": "content", "delta": accum[:-del_len]}
                                accum = accum[-del_len:]
                    else:
                        metadata_str += delta

        # Process final metadata payload
        if in_metadata:
            try:
                start_idx = metadata_str.find("{")
                end_idx = metadata_str.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    meta_json = json.loads(metadata_str[start_idx:end_idx+1])
                    yield {
                        "type": "metadata",
                        "citations": meta_json.get("citations", []),
                        "confidence_score": meta_json.get("confidence_score", 0.0),
                        "sufficient_context": meta_json.get("sufficient_context", True)
                    }
                    return
            except Exception as parse_ex:
                logger.error(f"Error parsing metadata JSON from stream: {str(parse_ex)}")
        
        # Fallback empty metadata if not parsed
        yield {"type": "metadata", "citations": [], "confidence_score": 0.0, "sufficient_context": False}

    def _parse_raw_llm_response(self, text: str) -> Dict[str, Any]:
        """
        Parses plain text outputs containing the metadata delimiter, returning structured responses.
        """
        delimiter = "||METADATA||"
        if delimiter in text:
            parts = text.split(delimiter)
            answer = parts[0].strip()
            metadata_str = parts[1].strip()
            
            try:
                start_idx = metadata_str.find("{")
                end_idx = metadata_str.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    meta_json = json.loads(metadata_str[start_idx:end_idx+1])
                    return {
                        "answer": answer,
                        "citations": meta_json.get("citations", []),
                        "confidence_score": meta_json.get("confidence_score", 0.0),
                        "sufficient_context": meta_json.get("sufficient_context", True)
                    }
            except Exception as e:
                logger.error(f"Failed to parse LLM metadata JSON: {str(e)}")
        
        # Fallback if no delimiter or JSON parse fails
        return {
            "answer": text,
            "citations": [],
            "confidence_score": 0.0,
            "sufficient_context": False
        }

gemini_service = GeminiService()
