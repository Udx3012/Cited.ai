import re
import logging
from typing import List, Dict, Any

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
            
            # Split page content into paragraphs
            paragraphs = [p.strip() for p in page_text.split("\n") if p.strip()]
            
            current_chunk_text = ""
            
            for para in paragraphs:
                # Check if this paragraph looks like a heading
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
                            "is_ocr": page["is_ocr"]
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
                        "is_ocr": page["is_ocr"]
                    }
                })
                chunk_index += 1

        logger.info(f"Created {len(chunks)} chunks from document '{filename}'.")
        return chunks
