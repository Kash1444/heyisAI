# app/services/ingestion_service.py
import logging
from app.services.gmail_service import gmail_service
from app.services.embedding_service import embedding_service
from app.db.vector_store import vector_store
from app.schemas.email import EmailIngestionStats

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Orchestrates the full email ingestion pipeline.

    Pipeline:
    1. Fetch emails from Gmail
    2. Extract clean text from each email
    3. Chunk text into smaller pieces
    4. Generate embeddings for each chunk
    5. Store chunks + embeddings in ChromaDB

    This service connects GmailService → EmbeddingService → VectorStore.
    It knows about all three but none of them know about each other.
    This is the Orchestrator pattern.
    """

    def ingest_emails(
        self,
        max_emails: int = 100,
        query: str = "",
    ) -> EmailIngestionStats:
        """
        Full ingestion pipeline — fetch, embed, store.

        Args:
            max_emails: how many emails to process
            query: optional Gmail filter (e.g. "after:2024/01/01")

        Returns:
            Stats about what was ingested
        """
        logger.info(
            f"Starting ingestion pipeline. "
            f"Max emails: {max_emails}, Query: '{query}'"
        )

        total_fetched = 0
        total_embedded = 0
        total_failed = 0

        # ── Step 1: Fetch emails from Gmail ───────────────────────────────
        logger.info("Step 1: Fetching emails from Gmail...")
        emails = gmail_service.list_emails(
            max_results=max_emails,
            query=query,
            label="",
        )

        total_fetched = len(emails)
        logger.info(f"Fetched {total_fetched} emails")

        if not emails:
            return EmailIngestionStats(
                total_fetched=0,
                total_embedded=0,
                total_failed=0,
                message="No emails found to ingest"
            )

        # ── Step 2-5: Process each email ──────────────────────────────────
        for i, email_meta in enumerate(emails):
            try:
                logger.info(
                    f"Processing email {i+1}/{total_fetched}: "
                    f"{email_meta.subject[:50]}"
                )

                # Step 2: Fetch full content
                full_email = gmail_service.get_email_full(email_meta.id)
                if not full_email:
                    logger.warning(f"Could not fetch full email {email_meta.id}")
                    total_failed += 1
                    continue

                # Step 3: Build text to embed
                # We combine subject + sender + body for richer embeddings
                # The subject and sender add crucial context to each chunk
                email_text = self._prepare_email_text(full_email)
                MAX_EMAIL_SIZE = 50000  # characters

                if len(email_text) > MAX_EMAIL_SIZE:
                    logger.warning(
                        f"Skipping large email {email_meta.id} "
                        f"({len(email_text)} chars)"
                    )
                    total_failed += 1
                    continue

                if not email_text.strip():
                    logger.warning(f"Empty email body for {email_meta.id}")
                    total_failed += 1
                    continue

                logger.info(
                    f"Email size: {len(email_text)} characters"
                )

                # Step 4: Chunk the text
                chunks = embedding_service.chunk_text(email_text)

                MAX_CHUNKS = 50

                if len(chunks) > MAX_CHUNKS:
                    logger.warning(
                        f"Too many chunks ({len(chunks)}). Truncating."
                    )
                    chunks = chunks[:MAX_CHUNKS]

                logger.debug(
                    f"Email chunked into {len(chunks)} pieces"
                )

                # Step 5: Embed all chunks at once (batch is faster)
                chunk_embeddings = embedding_service.embed_batch(chunks)

                # Step 6: Build metadata for each chunk
                # Metadata lets us filter search results later
                # e.g. "only search emails from amazon.com"
                chunk_ids = []
                chunk_metadatas = []

                for j, chunk in enumerate(chunks):
                    chunk_id = f"{email_meta.id}_chunk_{j}"
                    chunk_ids.append(chunk_id)
                    chunk_metadatas.append({
                        "email_id": email_meta.id,
                        "thread_id": email_meta.thread_id,
                        "subject": email_meta.subject,
                        "sender": email_meta.sender,
                        "date": email_meta.date,
                        "chunk_index": j,
                        "total_chunks": len(chunks),
                    })

                # Step 7: Store in ChromaDB
                vector_store.add_email_chunks_batch(
                    chunk_ids=chunk_ids,
                    texts=chunks,
                    embeddings=chunk_embeddings,
                    metadatas=chunk_metadatas,
                )

                total_embedded += 1

            except Exception as e:
                logger.error(
                    f"Failed to process email {email_meta.id}: {e}"
                )
                total_failed += 1
                continue

        stats = EmailIngestionStats(
            total_fetched=total_fetched,
            total_embedded=total_embedded,
            total_failed=total_failed,
            message=(
                f"Ingestion complete. "
                f"{total_embedded}/{total_fetched} emails embedded. "
                f"{total_failed} failed."
            )
        )

        logger.info(stats.message)

        # Log ChromaDB state after ingestion
        db_stats = vector_store.get_collection_stats()
        logger.info(
            f"ChromaDB now has {db_stats['total_chunks']} total chunks"
        )

        return stats

    def _prepare_email_text(self, email) -> str:
        """
        Build a clean text representation of an email for embedding.

        We prepend subject and sender to every chunk because:
        - Subject is the most important signal for retrieval
        - Sender helps when user asks "emails from Amazon"
        - Without this, chunks lose context about what email they're from

        This technique is called 'context injection' —
        adding surrounding context to improve embedding quality.
        """
        parts = []

        if email.subject:
            parts.append(f"Subject: {email.subject}")

        if email.sender:
            parts.append(f"From: {email.sender}")

        if email.date:
            parts.append(f"Date: {email.date}")

        # Prefer plain text over HTML
        # HTML has lots of tags that pollute the embedding
        body = email.body_text or email.body_html

        if body:
            # Basic HTML stripping if we only have HTML
            if not email.body_text and email.body_html:
                body = self._strip_html(body)
            parts.append(body)

        return "\n".join(parts)

    def _strip_html(self, html: str) -> str:
        """
        Remove HTML tags to get plain text.
        Simple version — good enough for Phase 1.
        """
        import re
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', ' ', html)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean


# Singleton
ingestion_service = IngestionService()