from fastapi import APIRouter, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from app.core.config import settings
from app.core.exceptions import APIKeyValidationError
from app.api.endpoints import ingestion, retrieval, chat

# Define API Key header dependency
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_backend_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise APIKeyValidationError("Missing X-API-Key authentication header")
    if api_key != settings.BACKEND_API_KEY:
        raise APIKeyValidationError("Invalid X-API-Key credentials")
    return api_key

# Main Router namespace
api_router = APIRouter(dependencies=[Depends(verify_backend_api_key)])

# Register sub-endpoints routers
api_router.include_router(ingestion.router, prefix="/ingest", tags=["Ingestion"])
api_router.include_router(retrieval.router, prefix="/retrieve", tags=["Retrieval"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat & Completions"])
