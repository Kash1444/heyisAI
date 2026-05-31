# app/services/retrieval_service.py

import logging
from dataclasses import dataclass
from app.services.embedding_service import embedding_service
from app.db.vector_store import vector_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """
    A single retrieved chunk with its context.
    Dataclass is perfect here — simple data container, no logic.
    """
    chunk_id: str
    text: str
    email_id: str
    subject: str
    sender: str
    date: str
    similarity_score: float  # 1 - distance, higher = more relevant


class RetrievalService:
    """
    Converts a user question into retrieved email chunks.

    Single responsibility: take a question, return relevant chunks.
    Does not generate answers — that's the RAG service's job.
    """

    def retrieve(
        self,
        question: str,
        n_results: int = 5,
        min_similarity: float = 0.2,
    ) -> list[RetrievedChunk]:
        """
        Find email chunks most relevant to the user's question.

        Args:
            question: the user's natural language question
            n_results: how many chunks to retrieve
            min_similarity: filter out weak matches below this threshold

        The min_similarity threshold is important.
        Without it, you always return n_results chunks even when
        none of them are relevant — leading to hallucinated answers.
        With it, you can return zero results and ask a clarification
        question instead of making something up.
        """
        if not question.strip():
            return []

        logger.info(f"Retrieving chunks for: '{question}'")

        # Step 1: Embed the question
        # The question and stored chunks use the same embedding model
        # so their vectors exist in the same mathematical space
        query_embedding = embedding_service.embed_text(question)

        # Step 2: Search ChromaDB
        raw_results = vector_store.search(
            query_embedding=query_embedding,
            n_results=n_results,
        )

        if not raw_results:
            logger.info("No chunks found in vector store")
            return []

        # Step 3: Convert to RetrievedChunk objects and filter
        chunks = []
        for result in raw_results:
            # Convert distance to similarity score
            # ChromaDB cosine distance: 0=identical, 2=opposite
            # Similarity: 1=identical, 0=unrelated
            similarity = 1 - result["distance"]

            if similarity < min_similarity:
                logger.debug(
                    f"Filtered out chunk with similarity {similarity:.3f}"
                )
                continue

            meta = result["metadata"]
            chunks.append(RetrievedChunk(
                chunk_id=result["id"],
                text=result["text"],
                email_id=meta.get("email_id", ""),
                subject=meta.get("subject", ""),
                sender=meta.get("sender", ""),
                date=meta.get("date", ""),
                similarity_score=round(similarity, 4),
            ))

        logger.info(
            f"Retrieved {len(chunks)} chunks above "
            f"similarity threshold {min_similarity}"
        )

        return chunks

    def deduplicate_by_email(
        self,
        chunks: list[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        """
        When multiple chunks from the same email are retrieved,
        keep only the highest-scoring chunk per email.

        Why? If you retrieved 5 chunks from the same email, you're
        wasting your context window. Better to have 5 different emails
        giving you diverse information.
        """
        seen_email_ids = {}

        for chunk in chunks:
            email_id = chunk.email_id
            if email_id not in seen_email_ids:
                seen_email_ids[email_id] = chunk
            else:
                # Keep the chunk with higher similarity
                if chunk.similarity_score > seen_email_ids[email_id].similarity_score:
                    seen_email_ids[email_id] = chunk

        deduplicated = list(seen_email_ids.values())
        deduplicated.sort(key=lambda x: x.similarity_score, reverse=True)

        return deduplicated


# Singleton
retrieval_service = RetrievalService()