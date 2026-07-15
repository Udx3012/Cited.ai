import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DocumentChunker:
    @staticmethod
    def chunk_document(
        parsed_pages: List[Dict[str, Any]], 
        document_id: str,
        filename: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Processes parsed pages and performs structure-aware paragraph chunking.
        Attempts to preserve headings, sentence boundaries, and attaches page-level metadata.
        Reads optional 'heading', 'title', and 'source_format' keys from each page dict
        to enrich chunk metadata (backward-compatible with PDF-only page dicts).
        """
        logger.info(f"Chunking document '{filename}' (ID: {document_id}) with size={chunk_size}, overlap={chunk_overlap}")
        chunks = []
        chunk_index = 0
        current_heading = "Introduction"  # Default fallback heading

        # Simple regex to detect typical document heading lines (e.g. "1. Section Name", "Section II:", "ARTICLE III")
        heading_pattern = re.compile(
            r"^(?:(?:[A-Z0-9\-\.\s]{1,8}\.)|(?:[IVXLCDM]{1,6}[\.\s:]+)|(?:Article\s+[0-9IVX]+)|(?:Section\s+[0-9A-Z]+))\s+([A-Z\w\s\-,]{3,60})$", 
            re.IGNORECASE
        )

        for page in parsed_pages:
            page_num = page["page_number"]
            page_text = page["text"]

            # Honour heading/title/source_format from richer parsers (DOCX, etc.);
            # fall back to regex detection for plain PDF pages.
            page_heading: Optional[str] = page.get("heading")
            page_title: Optional[str] = page.get("title")
            source_format: str = page.get("source_format", "pdf")
            is_ocr: bool = page.get("is_ocr", False)

            # Pre-seed heading from the page dict if available
            if page_heading:
                current_heading = page_heading
            
            # Split page content into paragraphs
            paragraphs = [p.strip() for p in page_text.split("\n") if p.strip()]
            
            current_chunk_text = ""
            
            for para in paragraphs:
                # Check if this paragraph looks like a heading (regex fallback for PDFs)
                if not page_heading:
                    heading_match = heading_pattern.match(para)
                    if heading_match:
                        current_heading = para
                        logger.debug(f"Detected heading: '{current_heading}' on page {page_num}")
                
                # If adding the paragraph exceeds chunk_size, emit the current chunk
                if len(current_chunk_text) + len(para) > chunk_size and current_chunk_text:
                    # Clean double spacing
                    clean_text = " ".join(current_chunk_text.split())
                    
                    chunks.append({
                        "id": f"{document_id}_{chunk_index}",
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "page_number": page_num,
                        "text": clean_text,
                        "metadata": {
                            "document_name": filename,
                            "page": page_num,
                            "heading": current_heading,
                            "is_ocr": is_ocr,
                            "source_format": source_format,
                            "title": page_title,
                        }
                    })
                    chunk_index += 1
                    
                    # Carry overlap text
                    overlap_start = max(0, len(current_chunk_text) - chunk_overlap)
                    current_chunk_text = current_chunk_text[overlap_start:] + " " + para
                else:
                    if current_chunk_text:
                        current_chunk_text += " " + para
                    else:
                        current_chunk_text = para

            # Flush remaining page text
            if current_chunk_text:
                clean_text = " ".join(current_chunk_text.split())
                chunks.append({
                    "id": f"{document_id}_{chunk_index}",
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "page_number": page_num,
                    "text": clean_text,
                    "metadata": {
                        "document_name": filename,
                        "page": page_num,
                        "heading": current_heading,
                        "is_ocr": is_ocr,
                        "source_format": source_format,
                        "title": page_title,
                    }
                })
                chunk_index += 1

        logger.info(f"Created {len(chunks)} chunks from document '{filename}'.")
        return chunks
