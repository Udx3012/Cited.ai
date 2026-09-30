from __future__ import annotations
import httpx
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)

class GroqService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model_name = getattr(settings, "GROQ_MODEL", "qwen/qwen3.8-27b")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient()

    def _build_prompts(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]], 
        history: Optional[List[Dict[str, str]]] = None,
        workspace_docs: Optional[List[Dict[str, Any]]] = None
    ) -> tuple:
        """
        Builds the system and user prompts for grounded RAG generation,
        incorporating workspace document catalog and multi-turn conversation history.
        """
        docs_catalog_lines = []
        if workspace_docs:
            for d in workspace_docs:
                name = d.get("document_name") or d.get("name", "Document")
                p_cnt = d.get("page_count") or d.get("pages", 1)
                c_cnt = d.get("chunk_count") or d.get("chunks", 0)
                docs_catalog_lines.append(f"- {name} ({p_cnt} pages, {c_cnt} chunks)")
        
        catalog_str = "\n".join(docs_catalog_lines) if docs_catalog_lines else "No documents currently uploaded."

        system_prompt = (
            "You are Cited.ai, an intelligent, articulate, and precise AI research assistant.\n"
            "Your objective is to provide comprehensive, accurate, and clearly formatted responses to the user's queries.\n\n"
            f"=== ACTIVE WORKSPACE DOCUMENTS ===\n"
            f"{catalog_str}\n"
            "==================================\n\n"
            "Answering Guidelines:\n"
            "1. Document Inventory & Status Queries:\n"
            "   - If the user asks what documents/files are uploaded, indexed, or available in the workspace, provide a clear, organized list based on the Active Workspace Documents catalog above.\n"
            "   - If the user asks whether a specific document is uploaded (e.g. 'is pba document uploaded', 'do you have pba?'):\n"
            "     * If a matching document exists in the catalog (e.g. 'pba exp 5.pdf'), confirm clearly that it is uploaded and available, and summarize its key contents using the provided context chunks.\n"
            "     * If no matching document exists in the catalog, inform the user clearly that it is not in the uploaded documents, and mention which documents are available.\n\n"
            "2. Grounded Content Answering & Citations:\n"
            "   - When answering questions about document contents, ground your claims strictly in the provided document context chunks.\n"
            "   - Each provided chunk begins with an index identifier like [Index: N]. Cite sources using bracketed numbers like [1], [2] at the end of each sentence or claim that uses information from that chunk.\n"
            "   - Cite only from the provided chunks. Never hallucinate facts outside the provided documents.\n\n"
            "3. Insufficient Context & Unknowns:\n"
            "   - If the user asks a substantive question about document contents but the provided document context chunks do not contain enough information, explain specifically what is or is not available in the documents, or state clearly: \"I do not have sufficient information in the provided documents to answer this question.\"\n"
            "   - When stating that context is insufficient, do not use any citation markers, and set sufficient_context to false, confidence_score to 0.0, citations to [].\n\n"
            "4. Multi-Turn Conversational Fluency:\n"
            "   - Understand conversational follow-ups, abbreviations, or single-word inquiries (e.g. 'pba?', 'contravault', 'tell me more', 'what about the salary?') within the context of prior messages and the workspace documents.\n\n"
            "5. General Greetings & App Inquiries:\n"
            "   - If the query is a general greeting, farewell, expression of gratitude, or general conversational chit-chat (e.g. 'hi', 'who are you', 'how does this work'), respond politely and intelligently without citations. Set sufficient_context to true, confidence_score to 1.0, and citations to [].\n\n"
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
        history: Optional[List[Dict[str, str]]] = None,
        workspace_docs: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
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

        system_prompt, user_prompt = self._build_prompts(query, context_chunks, history=history, workspace_docs=workspace_docs)
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0
        }

        logger.info(f"Submitting grounded generation request to Groq ({self.model_name})...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, json=payload, headers=self.headers, timeout=30.0)
                if response.status_code != 200:
                    logger.error(f"Groq completions failed: {response.status_code} - {response.text}")
                    raise Exception(f"Groq API error: {response.text}")
                
                result = response.json()
                raw_text = result["choices"][0]["message"]["content"] or ""
                
                return self._parse_raw_llm_response(raw_text, has_chunks=bool(context_chunks))
        except Exception as e:
            logger.error(f"Failed to query Groq LLM: {str(e)}")
            raise Exception(f"Failed to query grounded generator: {str(e)}")

    async def generate_grounded_answer_stream(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]],
        history: Optional[List[Dict[str, str]]] = None,
        workspace_docs: Optional[List[Dict[str, Any]]] = None
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

        system_prompt, user_prompt = self._build_prompts(query, context_chunks, history=history, workspace_docs=workspace_docs)
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

        logger.info("Submitting streaming completions request to Groq...")
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", self.api_url, json=payload, headers=self.headers, timeout=30.0) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error(f"Groq stream request failed: {response.status_code} - {error_body.decode()}")
                        raise Exception(f"Groq stream request failed: {response.status_code} - {error_body.decode()}")
                    
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
                                # Check for delimiter (case-insensitive and tolerant of whitespace)
                                import re
                                match = re.search(r"\|\|\s*METADATA\s*\|\|", accum, re.IGNORECASE)
                                if match:
                                    pre_text = accum[:match.start()]
                                    if pre_text:
                                        yield {"type": "content", "delta": pre_text}
                                    metadata_str = accum[match.end():]
                                    in_metadata = True
                                else:
                                    # Keep look-ahead window, yield the rest
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
            
            # If no delimiter was found in stream, try extracting JSON from trailing accumulator
            if accum:
                trailing_parsed = self._extract_metadata_json(accum, has_chunks=bool(context_chunks))
                yield trailing_parsed
                return

            # Fallback metadata
            yield {
                "type": "metadata",
                "citations": [],
                "confidence_score": 0.9 if not context_chunks else 0.0,
                "sufficient_context": not bool(context_chunks)
            }

        except Exception as e:
            logger.error(f"Network error in Groq stream connection: {str(e)}")
            raise e

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
            # Check for trailing ```json ... ``` block
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


from app.services.gemini import gemini_service

class GroundedGeneratorDispatcher:
    def __init__(self):
        self.groq = GroqService()
        self.gemini = gemini_service

    async def generate_grounded_answer(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]], 
        history: Optional[List[Dict[str, str]]] = None,
        workspace_docs: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generates grounded answer trying primary Groq LLM first, falling back to Gemini
        seamlessly if Groq encounters rate-limiting (429) or transient failure.
        """
        try:
            return await self.groq.generate_grounded_answer(
                query, context_chunks, history=history, workspace_docs=workspace_docs
            )
        except Exception as groq_err:
            logger.warning(f"Groq grounded generation failed: {str(groq_err)}. Attempting Gemini fallback...")
            is_valid_gemini = settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.startswith("AIza")
            if is_valid_gemini:
                try:
                    return await self.gemini.generate_grounded_answer(
                        query, context_chunks, history=history, workspace_docs=workspace_docs
                    )
                except Exception as gemini_err:
                    logger.error(f"Gemini fallback also failed: {str(gemini_err)}")
            raise groq_err

    async def generate_grounded_answer_stream(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]],
        history: Optional[List[Dict[str, str]]] = None,
        workspace_docs: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams response tokens trying primary Groq stream first, falling back to Gemini stream
        seamlessly if Groq fails to start.
        """
        try:
            async for event in self.groq.generate_grounded_answer_stream(
                query, context_chunks, history=history, workspace_docs=workspace_docs
            ):
                yield event
            return
        except Exception as groq_err:
            logger.warning(f"Groq streaming failed: {str(groq_err)}. Attempting Gemini streaming fallback...")
            is_valid_gemini = settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.startswith("AIza")
            if is_valid_gemini:
                try:
                    async for event in self.gemini.generate_grounded_answer_stream(
                        query, context_chunks, history=history, workspace_docs=workspace_docs
                    ):
                        yield event
                    return
                except Exception as gemini_err:
                    logger.error(f"Gemini fallback streaming also failed: {str(gemini_err)}")
            raise groq_err

# Export default instanced service (acts as dispatcher)
groq_service = GroundedGeneratorDispatcher()
