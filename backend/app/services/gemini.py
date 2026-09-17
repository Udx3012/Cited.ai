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

    def _build_prompts(self, query: str, context_chunks: List[Dict[str, Any]], history: Optional[List[Dict[str, str]]] = None) -> tuple:
        """
        Builds the system and user prompts for grounded RAG generation,
        incorporating conversation history for multi-turn context awareness.
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
            "Do not output any markdown formatting or extra text around the JSON metadata object."
        )

        context_str = ""
        for idx, chunk in enumerate(context_chunks):
            doc_name = chunk.get("document_name") or chunk.get("metadata", {}).get("document_name", "unknown")
            page_num = chunk.get("page") or chunk.get("page_number") or chunk.get("metadata", {}).get("page", 1)
            chunk_text = chunk.get("text", "")
            context_str += (
                f"[Index: {idx + 1}]\n"
                f"Source Document: {doc_name}\n"
                f"Page: {page_num}\n"
                f"Content: {chunk_text}\n"
                "-----------------------------------\n\n"
            )

        history_str = ""
        if history:
            valid_h = [h for h in history if h.get("content", "").strip()]
            if valid_h:
                lines = [f"{h.get('role', 'user').capitalize()}: {h.get('content', '').strip()}" for h in valid_h[-4:]]
                history_str = "Prior Conversation Context:\n" + "\n".join(lines) + "\n\n"

        user_prompt = (
            f"Provided Document Context Chunks:\n\n{context_str}"
            f"{history_str}"
            f"User Query Question: {query}"
        )

        return system_prompt, user_prompt

    async def generate_grounded_answer(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]], 
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Queries Gemini LLM (non-streaming mode) and returns a structured JSON answer payload.
        """
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is unconfigured. Returning mock answer payload.")
            return {
                "answer": "Gemini API key is unconfigured. Please configure GEMINI_API_KEY.",
                "citations": [],
                "confidence_score": 1.0,
                "sufficient_context": True
            }

        system_prompt, user_prompt = self._build_prompts(query, context_chunks, history=history)
        
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
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30.0)
            
            if response.status_code != 200:
                raise Exception(f"Gemini API returned error {response.status_code}: {response.text}")
            
            result = response.json()
            try:
                raw_text = result["candidates"][0]["content"]["parts"][0].get("text", "")
            except (KeyError, IndexError):
                raise Exception(f"Unexpected response format from Gemini API: {result}")
            
            return self._parse_raw_llm_response(raw_text, has_chunks=bool(context_chunks))

    async def generate_grounded_answer_stream(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]],
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams response tokens (SSE) for the answer text, 
        yielding citations and confidence scores as a metadata chunk at the end.
        """
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is unconfigured. Yielding mock stream payload.")
            yield {"type": "content", "delta": "Gemini API key is unconfigured. Please configure GEMINI_API_KEY."}
            yield {"type": "metadata", "citations": [], "confidence_score": 1.0, "sufficient_context": True}
            return

        system_prompt, user_prompt = self._build_prompts(query, context_chunks, history=history)
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
        
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", api_url, json=payload, headers={"Content-Type": "application/json"}, timeout=35.0) as response:
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
                        import re
                        match = re.search(r"\|\|\s*METADATA\s*\|\|", accum, re.IGNORECASE)
                        if match:
                            pre_text = accum[:match.start()]
                            if pre_text:
                                yield {"type": "content", "delta": pre_text}
                            metadata_str = accum[match.end():]
                            in_metadata = True
                        else:
                            if len(accum) > del_len * 2:
                                yield {"type": "content", "delta": accum[:-del_len * 2]}
                                accum = accum[-del_len * 2:]
                    else:
                        metadata_str += delta

        # Process final metadata payload
        if in_metadata or metadata_str:
            parsed = self._extract_metadata_json(metadata_str, has_chunks=bool(context_chunks))
            yield parsed
            return

        if accum:
            trailing_parsed = self._extract_metadata_json(accum, has_chunks=bool(context_chunks))
            yield trailing_parsed
            return
        
        # Fallback empty metadata if not parsed
        yield {
            "type": "metadata",
            "citations": [],
            "confidence_score": 0.9 if not context_chunks else 0.0,
            "sufficient_context": not bool(context_chunks)
        }

    def _extract_metadata_json(self, raw_str: str, has_chunks: bool = True) -> Dict[str, Any]:
        """
        Extracts and cleans JSON metadata from raw strings, ignoring markdown formatting.
        """
        import re
        clean_str = raw_str.replace("```json", "").replace("```", "").strip()
        start_idx = clean_str.find("{")
        end_idx = clean_str.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            try:
                meta_json = json.loads(clean_str[start_idx:end_idx+1])
                return {
                    "type": "metadata",
                    "citations": meta_json.get("citations", []),
                    "confidence_score": float(meta_json.get("confidence_score", 0.9 if not has_chunks else 0.8)),
                    "sufficient_context": bool(meta_json.get("sufficient_context", True))
                }
            except Exception as parse_ex:
                logger.warning(f"Failed to parse extracted metadata JSON: {str(parse_ex)}")

        return {
            "type": "metadata",
            "citations": [],
            "confidence_score": 0.9 if not has_chunks else 0.0,
            "sufficient_context": not has_chunks
        }

    def _parse_raw_llm_response(self, text: str, has_chunks: bool = True) -> Dict[str, Any]:
        """
        Parses plain text outputs containing the metadata delimiter, returning structured responses.
        Falls back to trailing codeblocks or inline citation scan [1], [2] if delimiter was skipped.
        """
        import re
        match = re.search(r"\|\|\s*METADATA\s*\|\|", text, re.IGNORECASE)
        answer = text
        citations = []
        confidence_score = 0.9 if not has_chunks else 0.85
        sufficient_context = True

        if match:
            answer = text[:match.start()].strip()
            metadata_str = text[match.end():].strip()
            meta_res = self._extract_metadata_json(metadata_str, has_chunks=has_chunks)
            citations = meta_res.get("citations", [])
            confidence_score = meta_res.get("confidence_score", 0.85)
            sufficient_context = meta_res.get("sufficient_context", True)
        else:
            code_block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
            if code_block_match:
                answer = text[:code_block_match.start()].strip()
                meta_res = self._extract_metadata_json(code_block_match.group(1), has_chunks=has_chunks)
                citations = meta_res.get("citations", [])
                confidence_score = meta_res.get("confidence_score", 0.85)
                sufficient_context = meta_res.get("sufficient_context", True)

        # Fallback: scan for [1], [2] citation markers if citations list is empty
        if not citations and has_chunks:
            marker_ids = sorted(list(set(int(m) for m in re.findall(r"\[(\d+)\]", answer))))
            for m_id in marker_ids:
                citations.append({
                    "id": m_id,
                    "matched_text": ""
                })

        return {
            "answer": answer,
            "citations": citations,
            "confidence_score": confidence_score if (citations or not has_chunks) else 0.5,
            "sufficient_context": sufficient_context
        }


gemini_service = GeminiService()
