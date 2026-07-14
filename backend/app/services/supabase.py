import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class SupabaseStorageService:
    def __init__(self):
        self.url = settings.SUPABASE_URL.rstrip('/') if settings.SUPABASE_URL else ""
        self.key = settings.SUPABASE_KEY
        self.bucket = settings.SUPABASE_BUCKET_NAME
        
        self.headers = {
            "Authorization": f"Bearer {self.key}" if self.key else "",
            "ApiKey": self.key if self.key else "",
        }

    async def upload_file(self, file_path: str, file_bytes: bytes, content_type: str = "application/pdf") -> str:
        """
        Uploads raw file bytes to Supabase Storage bucket.
        Returns the absolute storage URL.
        """
        if not self.url or not self.key or not self.bucket:
            logger.warning("Supabase storage variables are unconfigured. Returning mock URL path.")
            return f"https://mock-supabase.co/storage/v1/object/public/documents/{file_path}"
            
        endpoint = f"{self.url}/storage/v1/object/{self.bucket}/{file_path}"
        
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true"
        }
        
        logger.info(f"Uploading file to Supabase storage path: {self.bucket}/{file_path}")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint, content=file_bytes, headers=headers, timeout=30.0)
                if response.status_code not in (200, 201):
                    logger.error(f"Supabase upload failed: {response.status_code} - {response.text}")
                    raise Exception(f"Supabase Storage response: {response.text}")
                
                logger.info("Supabase storage upload completed successfully.")
                return f"{self.url}/storage/v1/object/public/{self.bucket}/{file_path}"
            except Exception as e:
                logger.error(f"Network error during Supabase upload: {str(e)}")
                raise Exception(f"Failed to upload document file to Supabase cloud storage: {str(e)}")

    async def delete_file(self, file_path: str) -> None:
        """
        Deletes a file from the Supabase Storage bucket.
        """
        if not self.url or not self.key or not self.bucket:
            logger.warning(f"[Mock Delete] Would delete file from Supabase storage path: {self.bucket}/{file_path}")
            return
            
        endpoint = f"{self.url}/storage/v1/object/{self.bucket}/{file_path}"
        
        logger.info(f"Deleting file from Supabase storage path: {self.bucket}/{file_path}")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(endpoint, headers=self.headers, timeout=30.0)
                if response.status_code not in (200, 204):
                    logger.error(f"Supabase delete failed: {response.status_code} - {response.text}")
                else:
                    logger.info("Supabase storage file deleted successfully.")
            except Exception as e:
                logger.error(f"Network error during Supabase delete: {str(e)}")

supabase_storage = SupabaseStorageService()
