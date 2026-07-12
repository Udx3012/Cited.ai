import uuid
import logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue
from app.core.config import settings

logger = logging.getLogger(__name__)

class QdrantService:
    def __init__(self):
        self.collection_name = "cited_chunks"
        self.url = settings.QDRANT_URL
        self.api_key = settings.QDRANT_API_KEY
        
        self.client = None
        if self.url:
            try:
                logger.info(f"Connecting to Qdrant Cloud at: {self.url}")
                self.client = QdrantClient(url=self.url, api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Qdrant client: {str(e)}")
        else:
            logger.warning("QDRANT_URL environment parameter is missing. Qdrant service is running in mock/dry-run mode.")

    def ensure_collection(self) -> None:
        """
        Ensures that the target Qdrant collection exists and is configured for 1024-dim Cosine vectors.
        """
        if not self.client:
            logger.warning("Qdrant client not initialized. Skipping collection check.")
            return

        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Collection '{self.collection_name}' not found. Creating collection with 1024 dimensions (Cosine)...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=1024,  # Matches bge-large-en-v1.5 vector size
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Collection '{self.collection_name}' successfully created.")
            else:
                logger.info(f"Verified Qdrant collection '{self.collection_name}' is ready.")
        except Exception as e:
            logger.error(f"Error checking/creating Qdrant collection: {str(e)}")
            raise Exception(f"Failed to initialize Qdrant vector database storage: {str(e)}")

    def upsert_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        """
        Upserts document chunk payload fields and dense vector embeddings into Qdrant.
        Converts custom string chunk IDs to valid UUID formats.
        """
        if not self.client:
            logger.warning(f"[Mock Indexing] Would upsert {len(chunks)} vectors to Qdrant collection.")
            return

        if len(chunks) != len(embeddings):
            raise ValueError("Size mismatch: The number of chunks must equal the number of embeddings.")

        points = []
        for chunk, vector in zip(chunks, embeddings):
            # Qdrant point IDs must be 64-bit integers or valid UUID strings.
            # We derive a deterministic UUID from our custom string chunk ID.
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["id"]))
            
            points.append(
                PointStruct(
                    id=point_uuid,
                    vector=vector,
                    payload={
                        "document_id": chunk["document_id"],
                        "chunk_index": chunk["chunk_index"],
                        "page_number": chunk["page_number"],
                        "text": chunk["text"],
                        "document_name": chunk["metadata"]["document_name"],
                        "heading": chunk["metadata"]["heading"],
                        "is_ocr": chunk["metadata"]["is_ocr"]
                    }
                )
            )

        try:
            logger.info(f"Upserting {len(points)} vector points into Qdrant collection '{self.collection_name}'...")
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info("Vector points successfully upserted to Qdrant Cloud.")
        except Exception as e:
            logger.error(f"Failed to upsert points to Qdrant: {str(e)}")
            raise Exception(f"Qdrant Database indexing failed: {str(e)}")

    def delete_document_vectors(self, document_id: str) -> None:
        """
        Deletes all vector points associated with the specified document_id.
        Prevents duplicates during re-indexing operations.
        """
        if not self.client:
            logger.warning(f"[Mock Delete] Would purge all vectors for document ID: {document_id}")
            return

        try:
            logger.info(f"Purging existing vectors for document ID: {document_id} from collection '{self.collection_name}'")
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            logger.info(f"Vectors for document {document_id} purged successfully.")
        except Exception as e:
            logger.error(f"Failed to delete document vectors from Qdrant: {str(e)}")
            raise Exception(f"Qdrant database point deletion failed: {str(e)}")

# Export default instanced service
qdrant_service = QdrantService()
