from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import RateLimitingMiddleware
from app.api.router import api_router
import logging

# Initialize structured logging configuration
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="The grounded RAG pipeline backend for Cited.AI, handling file ingestion and hybrid search.",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Global in-memory job tracker dictionary for background ingestion task status
app.state.ingestion_jobs = {}

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiter
app.add_middleware(RateLimitingMiddleware, limit_per_minute=100)

# Register global custom error handlers
register_exception_handlers(app)

# Include main router namespace mapped to /api/v1
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Cited.AI Backend. Initializing vector storage configuration...")
    
    # Assert settings values in production for AI/DB safety
    if settings.APP_ENV == "production":
        logger.info("Verifying production environment variables...")
        missing_vars = []
        if not settings.QDRANT_API_KEY: missing_vars.append("QDRANT_API_KEY")
        if not settings.GROQ_API_KEY: missing_vars.append("GROQ_API_KEY")
        if not settings.HF_API_KEY: missing_vars.append("HF_API_KEY")
        if not settings.SUPABASE_KEY: missing_vars.append("SUPABASE_KEY")
        
        if missing_vars:
            logger.error(f"Critical environment variables missing in production: {', '.join(missing_vars)}")
            raise RuntimeError(f"Missing required production environment keys: {', '.join(missing_vars)}")

    try:
        from app.services.qdrant import qdrant_service
        qdrant_service.ensure_collection()
        
        # Build BM25 index from previously uploaded vectors in Qdrant Cloud
        from app.retrieval.bm25 import bm25_service
        bm25_service.rebuild_index()
    except Exception as e:
        logger.error(f"Service initialization failed during startup: {str(e)}")

@app.get("/health", tags=["System Health"])
async def health_check():
    """
    Public health check endpoint. Render and other cloud runtimes 
    rely on this to verify that the service is operational.
    """
    logger.info("Health check endpoint pinged")
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV
    }

@app.get("/ready", tags=["System Health"])
async def readiness_check():
    """
    Readiness endpoint verifying dependencies (Qdrant & Supabase).
    """
    from app.services.qdrant import qdrant_service
    from app.services.supabase import supabase_storage

    qdrant_ok = qdrant_service.client is not None
    supabase_ok = supabase_storage.client is not None
    
    if not qdrant_ok or not supabase_ok:
        logger.error(f"Readiness check failed - Qdrant: {qdrant_ok}, Supabase: {supabase_ok}")
        raise HTTPException(status_code=503, detail="Service dependencies uninitialized")

    return {
        "status": "ready",
        "dependencies": {
            "qdrant": "connected" if qdrant_ok else "failed",
            "supabase": "connected" if supabase_ok else "failed"
        }
    }
