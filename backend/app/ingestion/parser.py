import io
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from pypdf import PdfReader
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

logger = logging.getLogger(__name__)

# Configure Windows Tesseract path fallbacks for local dev support
if sys.platform.startswith("win"):
    win_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe")
    ]
    for path in win_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.info(f"Configured Windows Tesseract path: {path}")
            break

class PDFParser:
    @staticmethod
    def parse_pdf(pdf_bytes: bytes, filename: str = "document.pdf") -> List[Dict[str, Any]]:
        """
        Parses a PDF from raw bytes page-by-page.
        Attempts native text extraction first, falling back to Tesseract OCR 
        if the page text length is below the text extraction threshold.
        """
        logger.info(f"Starting PDF parsing pipeline for: {filename}")
        parsed_pages = []
        
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            total_pages = len(reader.pages)
            logger.info(f"Document '{filename}' has {total_pages} total pages.")
            
            for idx in range(total_pages):
                page_num = idx + 1
                page = reader.pages[idx]
                
                # Attempt native text extraction
                extracted_text = ""
                try:
                    extracted_text = page.extract_text() or ""
                except Exception as ex:
                    logger.warning(f"Native text extraction failed on page {page_num}: {str(ex)}")
                
                # Calculate non-whitespace character count
                clean_text = "".join(extracted_text.split())
                is_ocr = False
                
                # If page is empty or text is extremely short, run OCR
                if len(clean_text) < 50:
                    logger.info(f"Page {page_num} text too short ({len(clean_text)} chars). Triggering OCR fallback...")
                    try:
                        # Render ONLY the current page as an image to keep RAM usage minimal
                        images = convert_from_bytes(
                            pdf_bytes, 
                            first_page=page_num, 
                            last_page=page_num,
                            fmt="jpeg"
                        )
                        if images:
                            pil_img = images[0]
                            # Run Tesseract OCR
                            ocr_text = pytesseract.image_to_string(pil_img) or ""
                            extracted_text = ocr_text.strip()
                            is_ocr = True
                            logger.info(f"OCR parsed {len(extracted_text)} chars on page {page_num}.")
                    except Exception as ocr_ex:
                        logger.error(f"OCR fallback failed on page {page_num}: {str(ocr_ex)}")
                        # If OCR fails, keep the original short text
                
                parsed_pages.append({
                    "page_number": page_num,
                    "text": extracted_text,
                    "is_ocr": is_ocr,
                    "source_format": "pdf",
                    "title": None,
                    "heading": None,
                })
                
            logger.info(f"Successfully parsed all {total_pages} pages for {filename}.")
            return parsed_pages
            
        except Exception as e:
            logger.error(f"Fatal error parsing PDF document {filename}: {str(e)}")
            raise Exception(f"Failed to parse PDF document bytes: {str(e)}")


# ---------------------------------------------------------------------------
# DOCX Parser
# ---------------------------------------------------------------------------

# Word heading style names that delimit logical sections
_DOCX_HEADING_STYLES = {
    "Heading 1", "Heading 2", "Heading 3",
    "heading 1", "heading 2", "heading 3",
}


class DocxParser:
    @staticmethod
    def parse_docx(docx_bytes: bytes, filename: str = "document.docx") -> List[Dict[str, Any]]:
        """
        Parses a DOCX file from raw bytes.

        Strategy:
        - Iterates over every paragraph in the document body.
        - Paragraphs whose style name matches a Word heading style start a new
          logical section (pseudo-page).
        - Each section is emitted as one page dict with the heading text in the
          'heading' metadata field, maintaining compatibility with DocumentChunker.

        Returns a list of page dicts in the same schema as PDFParser.
        """
        try:
            from docx import Document as DocxDocument  # python-docx
        except ImportError:
            raise ImportError(
                "python-docx is required for DOCX ingestion. "
                "Install it with: pip install python-docx"
            )

        logger.info(f"Starting DOCX parsing pipeline for: {filename}")

        try:
            doc = DocxDocument(io.BytesIO(docx_bytes))
        except Exception as e:
            logger.error(f"Failed to open DOCX document '{filename}': {str(e)}")
            raise Exception(f"Failed to parse DOCX document: {str(e)}")

        # Attempt to extract the document title from core properties
        doc_title: Optional[str] = None
        try:
            doc_title = doc.core_properties.title or None
        except Exception:
            pass

        parsed_pages: List[Dict[str, Any]] = []
        section_index = 0
        current_heading: Optional[str] = None
        current_paragraphs: List[str] = []

        def _flush_section(heading: Optional[str], paragraphs: List[str], section_num: int):
            """Emit buffered paragraphs as a page dict."""
            text = "\n".join(p for p in paragraphs if p.strip())
            parsed_pages.append({
                "page_number": section_num,
                "text": text,
                "is_ocr": False,
                "source_format": "docx",
                "title": doc_title,
                "heading": heading,
            })

        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ""
            para_text = para.text.strip()

            if style_name in _DOCX_HEADING_STYLES:
                # Flush the previous section before starting a new one
                if current_paragraphs or current_heading is not None:
                    section_index += 1
                    _flush_section(current_heading, current_paragraphs, section_index)
                    current_paragraphs = []
                current_heading = para_text if para_text else current_heading
            else:
                if para_text:
                    current_paragraphs.append(para_text)

        # Flush the final section
        section_index += 1
        _flush_section(current_heading, current_paragraphs, section_index)

        # Edge case: empty document
        if not parsed_pages:
            parsed_pages.append({
                "page_number": 1,
                "text": "",
                "is_ocr": False,
                "source_format": "docx",
                "title": doc_title,
                "heading": None,
            })

        logger.info(
            f"DOCX parsing complete for '{filename}': "
            f"{len(parsed_pages)} section(s), title='{doc_title}'."
        )
        return parsed_pages


# ---------------------------------------------------------------------------
# Unified DocumentParser dispatcher
# ---------------------------------------------------------------------------

class DocumentParser:
    """
    Dispatches to the appropriate parser based on detected file format.
    All parsers return the same normalized page-list schema.
    """

    @staticmethod
    def parse(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Detect the document format and delegate to the correct parser.

        Args:
            file_bytes: Raw binary content of the uploaded file.
            filename:   Original filename (used for format detection fallback and logging).

        Returns:
            List of page dicts: { page_number, text, is_ocr, source_format, title, heading }

        Raises:
            IngestionPipelineError: If the format is not supported.
        """
        from app.ingestion.format_detector import detect_format

        fmt = detect_format(filename, file_bytes)
        logger.info(f"Dispatching '{filename}' to {fmt.upper()} parser.")

        if fmt == "pdf":
            return PDFParser.parse_pdf(file_bytes, filename)
        elif fmt == "docx":
            return DocxParser.parse_docx(file_bytes, filename)
        else:
            # Should never reach here as detect_format raises for unknown types
            from app.core.exceptions import IngestionPipelineError
            raise IngestionPipelineError(f"No parser available for format: {fmt}")
