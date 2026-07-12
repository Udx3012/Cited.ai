import io
import os
import sys
import logging
from typing import List, Dict, Any
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
                    "is_ocr": is_ocr
                })
                
            logger.info(f"Successfully parsed all {total_pages} pages for {filename}.")
            return parsed_pages
            
        except Exception as e:
            logger.error(f"Fatal error parsing PDF document {filename}: {str(e)}")
            raise Exception(f"Failed to parse PDF document bytes: {str(e)}")
