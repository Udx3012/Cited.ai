import httpx
import json
import logging
from typing import List, Dict, Any, AsyncGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)

class GroqService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model_name = "llama-3.3-70b-versatile"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json"
        }

    def _build_prompts(self, query: str, context_chunks: List[Dict[str, Any]]) -> tuple:
        """
        Builds the system and user prompts for grounded RAG generation.
        """
        system_prompt = (
            "You are a helpful, extremely precise AI search assistant. Answer the user query using ONLY the provided document context chunks.\n"
            "Each chunk starts with an index identifier like [Index: N] where N is a number.\n"
            "Ground your answer strictly inside the provided context. Do not make assumptions or extrapolate beyond the text.\n"
            "Cite documents using their index numbers (e.g., [1], [2]) at the end of sentences that utilize that chunk's information.\n\n"
            "If the provided documents do not contain enough information to answer the query, follow these rules:\n"
            "1. State clearly: \"I do not have sufficient information in the provided documents to answer this question.\"\n"
            "2. Do not use any citation markers.\n"
            "3. Set sufficient_context to false, confidence_score to 0.0, and clear the citations array.\n\n"
            "Format your output as follows:\n"
            "Answer the query naturally, incorporating citation markers like [1], [2] at the end of sentences.\n"
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
                f"Source Document: {chunk['document_name']}\n"
                f"Page: {chunk['page']}\n"
                f"Chunk Index: {chunk['chunk_index']}\n"
                f"Content: {chunk['text']}\n"
                "-----------------------------------\n\n"
            )

        user_prompt = (
            f"Provided Document Context Chunks:\n\n{context_str}"
            f"User Query Question: {query}"
        )

        return system_prompt, user_prompt

    async def generate_grounded_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Queries Groq LLM (non-streaming mode) and returns a structured JSON answer payload.
        """
        if not self.api_key:
            logger.warning("GROQ_API_KEY is unconfigured. Returning mock answer payload.")
            return {
                "answer": "This is a mock RAG answer. Please configure GROQ_API_KEY to generate real grounded completions.",
                "citations": [],
                "confidence_score": 1.0,
                "sufficient_context": True
            }

        system_prompt, user_prompt = self._build_prompts(query, context_chunks)
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0
        }

        logger.info(f"Submitting grounded generation request to Groq ({self.model_name})...")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.api_url, json=payload, headers=self.headers, timeout=30.0)
                if response.status_code != 200:
                    logger.error(f"Groq completions failed: {response.status_code} - {response.text}")
                    raise Exception(f"Groq API error: {response.text}")
                
                result = response.json()
                raw_text = result["choices"][0]["message"]["content"] or ""
                
                return self._parse_raw_llm_response(raw_text)
            except Exception as e:
                logger.error(f"Failed to query Groq LLM: {str(e)}")
                raise Exception(f"Failed to query grounded generator: {str(e)}")

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
            logger.warning("GROQ_API_KEY is unconfigured. Yielding mock stream payload.")
            yield {"type": "content", "delta": "This is a mock streaming answer. Please configure your GROQ_API_KEY."}
            yield {"type": "metadata", "citations": [], "confidence_score": 1.0, "sufficient_context": True}
            return

        system_prompt, user_prompt = self._build_prompts(query, context_chunks)
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "stream": True
        }

        delimiter = "||METADATA||"
        del_len = len(delimiter)
        accum = ""
        in_metadata = False
        metadata_str = ""

        logger.info(f"Submitting streaming completions request to Groq...")
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", self.api_url, json=payload, headers=self.headers, timeout=30.0) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error(f"Groq stream request failed: {response.status_code} - {error_body.decode()}")
                        yield {"type": "content", "delta": "Failed to stream answer from generator."}
                        return
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            
                            try:
                                chunk_data = json.loads(data_str)
                                delta = chunk_data["choices"][0]["delta"].get("content", "")
                            except Exception:
                                continue

                            if not in_metadata:
                                accum += delta
                                if delimiter in accum:
                                    parts = accum.split(delimiter)
                                    # Yield preceding text
                                    if parts[0]:
                                        yield {"type": "content", "delta": parts[0]}
                                    metadata_str = parts[1]
                                    in_metadata = True
                                else:
                                    # Keep look-ahead window, yield the rest
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

            except Exception as e:
                logger.error(f"Network error in Groq stream connection: {str(e)}")
                yield {"type": "content", "delta": f"Stream connection interrupted: {str(e)}"}

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

# Export default instanced service
groq_service = GroqService()
