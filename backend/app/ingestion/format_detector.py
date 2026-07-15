import zipfile
import io
import logging
from app.core.exceptions import IngestionPipelineError

logger = logging.getLogger(__name__)

# Supported format identifiers
FORMAT_PDF = "pdf"
FORMAT_DOCX = "docx"

SUPPORTED_FORMATS = {FORMAT_PDF, FORMAT_DOCX}

SUPPORTED_EXTENSIONS = {
    ".pdf": FORMAT_PDF,
    ".docx": FORMAT_DOCX,
    ".doc": FORMAT_DOCX,
}

SUPPORTED_MIME_TYPES = {
    "application/pdf": FORMAT_PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FORMAT_DOCX,
    "application/msword": FORMAT_DOCX,
}

_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"


def _sniff_bytes(file_bytes: bytes) -> str | None:
    """
    Inspect the first bytes of the file to determine its format.
    Returns a FORMAT_* constant or None if unrecognised.
    """
    if file_bytes[:4] == _PDF_MAGIC:
        return FORMAT_PDF

    if file_bytes[:4] == _ZIP_MAGIC:
        # DOCX is a ZIP archive containing 'word/document.xml'
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                names = zf.namelist()
                if any(n.startswith("word/") for n in names):
                    return FORMAT_DOCX
        except (zipfile.BadZipFile, Exception):
            pass

    return None


def detect_format(filename: str, file_bytes: bytes) -> str:
    """
    Detect the document format from magic bytes, falling back to file extension.

    Returns one of: "pdf", "docx"
    Raises IngestionPipelineError for unsupported formats.
    """
    # 1. Try magic bytes (most reliable)
    fmt = _sniff_bytes(file_bytes)
    if fmt:
        logger.debug(f"Format detected via magic bytes: {fmt} for '{filename}'")
        return fmt

    # 2. Fall back to extension
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    fmt = SUPPORTED_EXTENSIONS.get(ext)
    if fmt:
        logger.debug(f"Format detected via extension '{ext}': {fmt} for '{filename}'")
        return fmt

    raise IngestionPipelineError(
        f"Unsupported file format for '{filename}'. "
        f"The ingestion pipeline accepts PDF (.pdf) and DOCX (.docx) documents only."
    )
