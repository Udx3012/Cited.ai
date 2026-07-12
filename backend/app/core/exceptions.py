from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

class RAGException(Exception):
    """Base exception for all Cited.ai internal pipeline errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class APIKeyValidationError(RAGException):
    """Exception raised when API authentication headers fail validation checks."""
    def __init__(self, message: str = "Invalid or missing BACKEND_API_KEY header"):
        super().__init__(message, status_code=401)

class IngestionPipelineError(RAGException):
    """Exception raised during file parsing, chunking, or indexing pipeline failures."""
    def __init__(self, message: str):
        super().__init__(message, status_code=422)

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RAGException)
    async def rag_exception_handler(request: Request, exc: RAGException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "type": exc.__class__.__name__,
                    "message": exc.message
                }
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "type": "HTTPException",
                    "message": exc.detail
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = " -> ".join(str(x) for x in err.get("loc", []))
            errors.append(f"{loc}: {err.get('msg')}")
            
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "type": "ValidationError",
                    "message": "Request payload schema validation failed.",
                    "details": errors
                }
            }
        )
