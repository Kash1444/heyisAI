# app/services/embedding_service.py

import logging
from sentence_transformers import SentenceTransformer
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Converts text into vector embeddings using a local model.

    We use sentence-transformers with 'all-MiniLM-L6-v2'.
    Why this model?
    - Free: runs locally, no API cost
    - Fast: small model, quick inference
    - Good quality: 384 dimensions, strong semantic understanding
    - Industry standard for RAG prototypes

    Later you could swap to OpenAI text-embedding-3-small or
    Google's embedding model — the interface stays the same.
    That's the value of wrapping it in a service class.
    """

    def __init__(self):
        self._model = None  # Lazy load — don't load until first use

    def _get_model(self) -> SentenceTransformer:
        """
        Lazy load the embedding model.

        Why lazy? The model takes ~2 seconds to load into memory.
        We don't want app startup to be slow.
        First call loads it. Every subsequent call reuses it.
        This is the lazy initialization pattern.
        """
        if self._model is None:
            logger.info(
                f"Loading embedding model: {settings.embedding_model}"
            )
            self._model = SentenceTransformer(settings.embedding_model)
            logger.info("Embedding model loaded successfully")
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """
        Convert a single text string into an embedding vector.

        Returns a list of floats (384 dimensions for MiniLM).
        This is what gets stored in ChromaDB.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        model = self._get_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()  # ChromaDB expects a plain list

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts at once.

        Always prefer batch over calling embed_text in a loop.
        Why? The model processes batches more efficiently using
        GPU/CPU parallelism. A batch of 32 texts takes roughly
        the same time as a batch of 4 — not 8x longer.
        """
        if not texts:
            return []

        # Filter out empty strings
        clean_texts = [t.strip() for t in texts if t and t.strip()]

        if not clean_texts:
            return []

        model = self._get_model()
        logger.info(f"Embedding batch of {len(clean_texts)} texts...")

        embeddings = model.encode(
            clean_texts,
            convert_to_numpy=True,
            # show bar for large batches
            show_progress_bar=len(clean_texts) > 50,
            batch_size=32,
        )

        logger.info("Batch embedding complete")
        return [e.tolist() for e in embeddings]

    def chunk_text(
        self,
        text: str,
        chunk_size: int = None,
        overlap: int = 100
    ) -> list[str]:
        """
        Split long text into overlapping chunks.

        Why overlap? Imagine a sentence spans two chunks:
        Chunk 1: "...your train departs from Chennai"
        Chunk 2: "Central station at 6:00 AM on Monday..."

        Without overlap, the critical context is split.
        With overlap, each chunk contains a window of surrounding text.

        Args:
            text: the text to chunk
            chunk_size: max characters per chunk
            overlap: how many chars to repeat between chunks
        """
        if chunk_size is None:
            chunk_size = settings.email_chunk_size

        if not text or len(text) <= chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Don't cut in the middle of a word
            # Look back for the last space within the chunk
            if end < len(text):
                last_space = text.rfind(" ", start, end)
                if last_space > start:
                    end = last_space

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move forward by chunk_size minus overlap
            # This creates the overlap window
            start = end - overlap
            if start >= len(text):
                break

        return chunks


# Singleton
embedding_service = EmbeddingService()
