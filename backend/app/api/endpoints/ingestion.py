from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, Request, HTTPException
from app.schemas.ingestion import UploadResponse, JobStatusResponse, IngestionStatusResponse
from app.core.exceptions import IngestionPipelineError, RAGException
from app.services.supabase import supabase_storage
from app.ingestion.parser import PDFParser
from app.ingestion.chunker import DocumentChunker
from app.embeddings.embedder import hf_embedder
from app.services.qdrant import qdrant_service
from app.retrieval.bm25 import bm25_service
import uuid
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

def sync_run_ingestion(job_id: str, document_id: str, filename: str, file_bytes: bytes, jobs_db: dict):
    """
    Ingestion worker running PDF parsing, text chunking, embedding generation via Hugging Face,
    and batch vector uploads into Qdrant Cloud.
    """
    try:
        logger.info(f"Ingestion worker started for job {job_id}")
        jobs_db[job_id]["status"] = "processing"
        jobs_db[job_id]["progress"] = 5

        # Clean existing vectors to support clean, idempotent re-indexing of this document
        qdrant_service.delete_document_vectors(document_id)
        jobs_db[job_id]["progress"] = 10

        # Step 1: Parse PDF with OCR Fallbacks
        parsed_pages = PDFParser.parse_pdf(file_bytes, filename)
        jobs_db[job_id]["pages"] = len(parsed_pages)
        jobs_db[job_id]["progress"] = 40

        # Step 2: Document Chunking
        chunks = DocumentChunker.chunk_document(parsed_pages, document_id, filename)
        jobs_db[job_id]["chunks"] = len(chunks)
        jobs_db[job_id]["progress"] = 55

        # Step 3: Batch Embeddings Generation & Qdrant Upsert
        if chunks:
            batch_size = 16
            embeddings = []
            total_chunks = len(chunks)
            
            logger.info(f"Generating embeddings for {total_chunks} chunks in batches of {batch_size}")
            for i in range(0, total_chunks, batch_size):
                batch_chunks = chunks[i:i + batch_size]
                batch_texts = [c["text"] for c in batch_chunks]
                
                # Fetch embeddings via serverless API
                # embed_documents is async; use asyncio.run() since this worker runs in a sync background thread
                batch_embeddings = asyncio.run(hf_embedder.embed_documents(batch_texts))
                embeddings.extend(batch_embeddings)
                
                # Incrementally scale progress from 55% to 85%
                progress_step = int(55 + (len(embeddings) / total_chunks) * 30)
                jobs_db[job_id]["progress"] = min(85, progress_step)

            # Upload vectors and metadata payloads to Qdrant Cloud
            jobs_db[job_id]["progress"] = 90
            qdrant_service.upsert_chunks(chunks, embeddings)
            
        # Step 4: Rebuild in-memory BM25 lexical index to register new document chunks
        jobs_db[job_id]["progress"] = 95
        bm25_service.rebuild_index()

        jobs_db[job_id]["progress"] = 100
        jobs_db[job_id]["status"] = "completed"
        logger.info(f"Ingestion worker finished successfully for job {job_id}")
    except Exception as e:
        logger.error(f"Ingestion worker encountered error in job {job_id}: {str(e)}")
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["error_message"] = str(e)

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Validates the uploaded file, saves it to Supabase Storage,
    and triggers the background PDF parsing and ingestion pipeline.
    """
    # 1. Validate PDF file extension and MIME type
    if not file.filename.lower().endswith(".pdf") or file.content_type != "application/pdf":
        raise IngestionPipelineError(
            message=f"Invalid file format '{file.filename}'. Ingestion pipeline only accepts PDF documents."
        )

    document_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    
    try:
        # Read file bytes
        file_bytes = await file.read()
        
        # Validate File Size (Max 50MB)
        if len(file_bytes) > 52428800:
            raise IngestionPipelineError("File size exceeds the 50MB production limit.")

        # Sanitize filename to mitigate directory traversal & scripting vectors
        import re
        raw_filename = file.filename or "document.pdf"
        safe_filename = re.sub(r"[^\w\.\-]", "_", raw_filename)
        if not safe_filename or safe_filename.startswith("..") or safe_filename == ".":
            safe_filename = f"document_{uuid.uuid4().hex[:6]}.pdf"

        # 2. Upload file to Supabase Storage
        secure_path = f"{document_id}/{safe_filename}"
        storage_url = await supabase_storage.upload_file(secure_path, file_bytes, "application/pdf")
        
        # 3. Initialize background job progress state
        request.app.state.ingestion_jobs[job_id] = {
            "success": True,
            "job_id": job_id,
            "document_id": document_id,
            "status": "queued",
            "progress": 0,
            "pages": 0,
            "chunks": 0,
            "error_message": None
        }

        # 4. Trigger asynchronous ingestion job
        background_tasks.add_task(
            sync_run_ingestion,
            job_id,
            document_id,
            safe_filename,
            file_bytes,
            request.app.state.ingestion_jobs
        )

        return UploadResponse(
            success=True,
            job_id=job_id,
            document_id=document_id,
            filename=safe_filename,
            storage_url=storage_url,
            message="Document uploaded and queued for vector index ingestion successfully."
        )
    except RAGException as re_ex:
        raise re_ex
    except Exception as e:
        logger.error(f"Failed to initiate ingestion pipeline: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate ingestion pipeline: {str(e)}"
        )

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(request: Request, job_id: str):
    """
    Checks the status and progress of a background ingestion job.
    """
    jobs_db = request.app.state.ingestion_jobs
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Ingestion job not found or expired")
    
    job_info = jobs_db[job_id]
    return JobStatusResponse(**job_info)

@router.delete("/document/{document_id}", response_model=IngestionStatusResponse)
async def delete_document(document_id: str):
    """
    Purges document metadata and all corresponding vector chunk records from Qdrant database,
    deletes raw document from Supabase Storage, and rebuilds the in-memory BM25 index.
    """
    try:
        # 1. Retrieve the document name from Qdrant first so we know what filename to delete in Supabase
        filename = qdrant_service.get_document_name(document_id)
        
        # 2. Purge vector points from Qdrant
        qdrant_service.delete_document_vectors(document_id)
        
        # 3. Rebuild lexical index to remove references to the deleted document
        bm25_service.rebuild_index()
        
        # 4. If we found a filename in Qdrant, delete the file from Supabase Storage
        if filename:
            import re
            safe_filename = re.sub(r"[^\w\.\-]", "_", filename)
            secure_path = f"{document_id}/{safe_filename}"
            await supabase_storage.delete_file(secure_path)
            message = f"Document {filename} ({document_id}) and all related vector chunks purged successfully from Qdrant and Supabase Storage."
        else:
            logger.warning(f"Could not resolve filename for document {document_id} from Qdrant. Supabase raw file delete bypassed.")
            message = f"Document {document_id} and all related vector chunks purged successfully from Qdrant Cloud. Supabase file delete bypassed."

        return IngestionStatusResponse(
            success=True,
            message=message
        )
    except Exception as e:
        logger.error(f"Failed to purge document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to purge document vectors: {str(e)}"
        )
