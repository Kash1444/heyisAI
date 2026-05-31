# app/services/gmail_service.py

import base64
import logging
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.gmail_auth_service import gmail_auth_service
from app.schemas.email import EmailMetadata, EmailFull

logger = logging.getLogger(__name__)


class GmailService:
    """
    Handles all Gmail API interactions.

    Responsibilities:
    - List emails
    - Search emails by query
    - Fetch full email content
    - Parse raw Gmail API response into clean Python objects

    Does NOT handle:
    - Authentication (that's GmailAuthService)
    - Embeddings (that's EmbeddingService)
    - AI generation (that's ChatService)
    """
    """Handles all Gmail API interactions."""

    def __init__(self):
        self._client = None
        self._client_token = None

    def _get_gmail_client(self):
        """
        Return authenticated Gmail client.

        Rebuild only when token changes.
        """

        credentials = gmail_auth_service.get_valid_credentials()

        if not credentials:
            raise ValueError(
                "No valid credentials found. "
                "User must authenticate at /auth/login"
            )

        current_token = credentials.token

        if (
            self._client is None
            or self._client_token != current_token
        ):
            self._client = build(
                "gmail",
                "v1",
                credentials=credentials
            )

            self._client_token = current_token

            logger.debug(
                "Gmail client rebuilt with fresh credentials"
            )

        return self._client

    # ── Fetching Emails ────────────────────────────────────────────────────

    def list_emails(
        self,
        max_results: int = 20,
        query: str = "",
        label: str = "INBOX"
    ) -> list[EmailMetadata]:
        """
        List emails from Gmail.

        Args:
            max_results: how many emails to return
            query: Gmail search query (e.g. "from:amazon subject:order")
            label: which mailbox (INBOX, SENT, SPAM, etc.)

        Returns:
            List of EmailMetadata objects (no body content)

        Two API calls happen here:
        1. messages.list → get list of email IDs
        2. messages.get  → get details for each ID
        This is how Gmail API works — you always list first, then fetch.
        """
        try:
            service = self._get_gmail_client()

            # Step 1: Get list of message IDs
            list_params = {
                "userId": "me",  # "me" means the authenticated user
                "maxResults": max_results,
            }

            if query:
                list_params["q"] = query
            if label:
                list_params["labelIds"] = [label]

            result = service.users().messages().list(**list_params).execute()
            messages = result.get("messages", [])

            if not messages:
                logger.info("No emails found for query")
                return []

            # Step 2: Fetch metadata for each message ID
            emails = []
            for msg in messages:
                try:
                    email = self.get_email_metadata(msg["id"])
                    if email:
                        emails.append(email)
                except Exception as e:
                    logger.warning(f"Failed to fetch email {msg['id']}: {e}")
                    continue

            logger.info(f"Listed {len(emails)} emails")
            return emails

        except HttpError as e:
            logger.error(f"Gmail API error listing emails: {e}")
            raise

    def get_email_metadata(self, email_id: str) -> Optional[EmailMetadata]:
        """
        Fetch lightweight metadata for a single email.
        Uses 'metadata' format — faster, less data transfer.
        """
        try:
            service = self._get_gmail_client()

            # format='metadata' fetches only headers, not body
            # This is much faster for listing purposes
            message = service.users().messages().get(
                userId="me",
                id=email_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"]
            ).execute()

            return self._parse_metadata(message)

        except HttpError as e:
            logger.error(f"Failed to get email metadata {email_id}: {e}")
            return None

    def get_email_full(self, email_id: str) -> Optional[EmailFull]:
        """
        Fetch complete email including decoded body.
        Uses 'full' format — slower but complete.
        """
        try:
            service = self._get_gmail_client()

            message = service.users().messages().get(
                userId="me",
                id=email_id,
                format="full"
            ).execute()

            return self._parse_full_email(message)

        except HttpError as e:
            logger.error(f"Failed to get full email {email_id}: {e}")
            return None

    def search_emails(
        self,
        query: str,
        max_results: int = 20
    ) -> list[EmailMetadata]:
        """
        Search emails using Gmail's native search syntax.

        Gmail query examples:
        - "from:amazon.com"
        - "subject:order confirmation"
        - "after:2024/01/01 before:2024/12/31"
        - "has:attachment filename:pdf"

        Note: This is keyword/filter search, NOT semantic search.
        Semantic search comes later with our vector database.
        Both have their place — keyword search for exact queries,
        semantic search for meaning-based queries.
        """
        logger.info(f"Searching Gmail with query: '{query}'")
        return self.list_emails(
            query=query,
            max_results=max_results,
            label=""  # search across all labels
        )

    # ── Parsing ────────────────────────────────────────────────────────────

    def _parse_metadata(self, message: dict) -> EmailMetadata:
        """
        Parse Gmail API message object into our EmailMetadata schema.

        The Gmail API returns headers as a list of {name, value} dicts:
        [
            {"name": "From", "value": "sender@gmail.com"},
            {"name": "Subject", "value": "Hello"},
            ...
        ]

        We convert this into a clean Python object.
        """
        headers = message.get("payload", {}).get("headers", [])

        # Convert header list into a lookup dict
        # {"From": "sender@gmail.com", "Subject": "Hello", ...}
        header_map = {
            h["name"]: h["value"]
            for h in headers
        }

        return EmailMetadata(
            id=message["id"],
            thread_id=message["threadId"],
            subject=header_map.get("Subject", "(no subject)"),
            sender=header_map.get("From", "unknown"),
            recipient=header_map.get("To", "unknown"),
            date=header_map.get("Date", "unknown"),
            snippet=message.get("snippet", ""),
            labels=message.get("labelIds", []),
        )

    def _parse_full_email(self, message: dict) -> EmailFull:
        """
        Parse a full Gmail message including decoded body.

        Email body is base64url encoded by Gmail.
        We decode it to get the actual text content.

        Handles two email structures:
        1. Simple email — body directly in payload.body.data
        2. Multipart email — body split across payload.parts[]
        (common for emails with both text and html versions)
        """
        # First parse all the metadata fields
        metadata = self._parse_metadata(message)

        # Then extract body
        payload = message.get("payload", {})
        body_text = ""
        body_html = ""

        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            # Simple plain text email
            body_text = self._decode_body(
                payload.get("body", {}).get("data", "")
            )

        elif mime_type == "text/html":
            # Simple HTML email
            body_html = self._decode_body(
                payload.get("body", {}).get("data", "")
            )

        elif "multipart" in mime_type:
            # Multipart email — has multiple parts
            # Common structure: part[0]=text/plain, part[1]=text/html
            parts = payload.get("parts", [])
            body_text, body_html = self._extract_multipart_body(parts)

        return EmailFull(
            **metadata.model_dump(),
            body_text=body_text,
            body_html=body_html,
        )

    def _extract_multipart_body(
        self,
        parts: list
    ) -> tuple[str, str]:
        """
        Recursively extract text and html from multipart email parts.

        Why recursive? Because emails can be nested:
        multipart/mixed
        └── multipart/alternative
            ├── text/plain
            └── text/html
        """
        body_text = ""
        body_html = ""

        for part in parts:
            mime_type = part.get("mimeType", "")

            if mime_type == "text/plain":
                body_text = self._decode_body(
                    part.get("body", {}).get("data", "")
                )
            elif mime_type == "text/html":
                body_html = self._decode_body(
                    part.get("body", {}).get("data", "")
                )
            elif "multipart" in mime_type:
                # Recurse into nested multipart
                nested_parts = part.get("parts", [])
                text, html = self._extract_multipart_body(nested_parts)
                body_text = body_text or text
                body_html = body_html or html

        return body_text, body_html

    def _decode_body(self, data: str) -> str:
        """
        Decode base64url encoded email body.

        Gmail encodes email body as base64url (not standard base64).
        The difference: base64url uses - and _ instead of + and /
        Python's base64 module handles this with urlsafe_b64decode.
        """
        if not data:
            return ""

        try:
            # Add padding if needed (base64 requires length % 4 == 0)
            padded = data + "=" * (4 - len(data) % 4)
            decoded_bytes = base64.urlsafe_b64decode(padded)
            return decoded_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Failed to decode email body: {e}")
            return ""


# Singleton
gmail_service = GmailService()