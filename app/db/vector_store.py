# app/db/vector_store.py

import logging
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings

logger = logging.getLogger(__name__)

# Name of our collection inside ChromaDB
# Think of this like a table name in a relational database
EMAILS_COLLECTION = "emails"


class VectorStore:
    """
    Abstraction over ChromaDB for storing and searching email embeddings.

    Why abstract it into a class?
    If you later switch to pgvector or Pinecone, you only
    change this file. Everything that calls VectorStore
    stays exactly the same. This is the Adapter pattern.

    ChromaDB concepts:
    - Collection: a named group of embeddings (like a table)
    - Document: the original text that was embedded
    - Embedding: the vector representation of the document
    - Metadata: structured data stored alongside the embedding
    - ID: unique identifier for each stored item
    """

    def __init__(self):
        self._client = None
        self._collection = None

    def _get_collection(self):
        """
        Lazy initialize ChromaDB client and collection.
        Same pattern as the embedding model — load on first use.
        """
        if self._collection is None:
            logger.info(
                f"Initializing ChromaDB at: {settings.chroma_persist_dir}"
            )

            # PersistentClient stores data to disk
            # Data survives app restarts — critical for production
            self._client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False)
            )

            # get_or_create — safe to call multiple times
            # Won't fail if collection already exists
            self._collection = self._client.get_or_create_collection(
                name=EMAILS_COLLECTION,
                metadata={
                    "description": "Gmail email embeddings",
                    "hnsw:space": "cosine",  # cosine similarity for text
                }
            )

            count = self._collection.count()
            logger.info(
                f"ChromaDB ready. Collection '{EMAILS_COLLECTION}' "
                f"has {count} documents"
            )

        return self._collection

    def add_email_chunk(
        self,
        chunk_id: str,
        text: str,
        embedding: list[float],
        metadata: dict,
    ):
        """
        Store a single email chunk with its embedding.

        Args:
            chunk_id: unique ID for this chunk (e.g. "email_id_chunk_0")
            text: the actual text content of the chunk
            embedding: the vector representation
            metadata: structured data for filtering later
            (email_id, subject, sender, date, etc.)
        """
        collection = self._get_collection()

        collection.upsert(  # upsert = insert or update if ID exists
            ids=[chunk_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def add_email_chunks_batch(
        self,
        chunk_ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ):
        """
        Store multiple chunks at once — always prefer this over
        calling add_email_chunk in a loop for large ingestions.
        """
        if not chunk_ids:
            return

        collection = self._get_collection()

        collection.upsert(
            ids=chunk_ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(f"Stored {len(chunk_ids)} chunks in ChromaDB")

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Find the most semantically similar chunks to a query.

        Args:
            query_embedding: the embedding of the user's question
            n_results: how many results to return
            where: optional metadata filter
                   e.g. {"sender": "amazon@amazon.com"}

        Returns:
            List of dicts with keys:
            - id: chunk ID
            - text: original chunk text
            - metadata: stored metadata
            - distance: similarity score (lower = more similar)
        """
        collection = self._get_collection()

        # Check we have enough documents to search
        count = collection.count()
        if count == 0:
            logger.warning("Vector store is empty. Run ingestion first.")
            return []

        # Limit n_results to what's available
        n_results = min(n_results, count)

        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }

        if where:
            query_params["where"] = where

        results = collection.query(**query_params)

        # ChromaDB returns parallel lists — restructure into list of dicts
        # This makes it much easier to work with downstream
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })

        return formatted

    def get_collection_stats(self) -> dict:
        """How many chunks are stored?"""
        collection = self._get_collection()
        return {
            "total_chunks": collection.count(),
            "collection_name": EMAILS_COLLECTION,
            "persist_dir": settings.chroma_persist_dir,
        }

    def delete_email(self, email_id: str):
        """
        Delete all chunks for a specific email.
        Useful when an email is deleted or needs re-indexing.
        """
        collection = self._get_collection()

        collection.delete(
            where={"email_id": email_id}
        )
        logger.info(f"Deleted chunks for email {email_id}")


# Singleton
vector_store = VectorStore()