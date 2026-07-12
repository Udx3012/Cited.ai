import logging
import sys
import os
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logging() -> None:
    logger = logging.getLogger()
    
    # Set default log level based on environment config
    debug_mode = os.getenv("DEBUG", "true").lower() == "true"
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    
    # In production, use JSON format. For development, use human-readable terminal output.
    app_env = os.getenv("APP_ENV", "development")
    if app_env == "production":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    handler.setFormatter(formatter)
    
    # Replace existing handlers with our custom stream handler
    logger.handlers = [handler]
    
    # Silence third-party verbose logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
