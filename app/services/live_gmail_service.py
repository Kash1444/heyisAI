# app/services/live_gmail_service.py
#
# Fetches emails LIVE from Gmail API on every query.
# No pre-ingestion. No ChromaDB. Direct Gmail access.
# This is the heart of the new architecture.

import base64
import logging
from typing import Optional
from googleapiclient.discovery import build
from app.services.gmail_auth_service import gmail_auth_service

logger = logging.getLogger(__name__)


class LiveGmailService:
    """
    Searches and fetches emails directly from Gmail API.

    Key design decision: fetch only what we need.
    We never download your entire inbox.
    We search first, then fetch only the matching emails.

    Gmail API rate limits:
    - 250 quota units per second per user
    - messages.list = 5 units
    - messages.get  = 5 units
    So 10 emails = ~55 units. Well within limits.
    """

    def _get_client(self):
        credentials = gmail_auth_service.get_valid_credentials()
        if not credentials:
            raise ValueError("Not authenticated. Visit /auth/login")
        return build("gmail", "v1", credentials=credentials)

    def search_and_fetch(
        self,
        queries: list[str],
        max_per_query: int = 10,
    ) -> list[dict]:
        """
        Run multiple Gmail queries and return deduplicated emails.

        Why multiple queries?
        A single query might miss relevant emails.
        Running "from:amazon.com" AND "subject:order" separately
        gives broader coverage than either alone.

        Deduplication ensures the same email isn't returned twice
        even if it matches multiple queries.
        """
        seen_ids = set()
        all_emails = []

        for query in queries:
            try:
                emails = self._search_one_query(query, max_per_query)
                for email in emails:
                    if email["id"] not in seen_ids:
                        seen_ids.add(email["id"])
                        all_emails.append(email)
            except Exception as e:
                logger.warning(f"Query '{query}' failed: {e}")
                continue

        logger.info(f"Total unique emails fetched: {len(all_emails)}")
        return all_emails

    def _search_one_query(
        self,
        query: str,
        max_results: int
    ) -> list[dict]:
        """Search Gmail with one query and fetch full content."""
        service = self._get_client()

        # Step 1: Get matching message IDs
        result = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
        ).execute()

        messages = result.get("messages", [])
        if not messages:
            logger.info(f"No results for query: '{query}'")
            return []

        logger.info(f"Query '{query}' → {len(messages)} messages")

        # Step 2: Fetch full content for each ID
        emails = []
        for msg in messages:
            email = self._fetch_email(service, msg["id"])
            if email:
                emails.append(email)

        return emails

    def _fetch_email(
        self,
        service,
        email_id: str
    ) -> Optional[dict]:
        """
        Fetch one complete email and parse it into a clean dict.
        Returns None if fetch fails — we skip and continue.
        """
        try:
            message = service.users().messages().get(
                userId="me",
                id=email_id,
                format="full",
            ).execute()

            return self._parse_email(message)

        except Exception as e:
            logger.warning(f"Failed to fetch email {email_id}: {e}")
            return None

    def _parse_email(self, message: dict) -> dict:
        """Parse raw Gmail API message into clean dict."""
        payload = message.get("payload", {})
        headers = payload.get("headers", [])

        # Convert header list to dict for easy lookup
        header_map = {h["name"]: h["value"] for h in headers}

        # Extract body
        body = self._extract_body(payload)

        return {
            "id": message["id"],
            "thread_id": message["threadId"],
            "subject": header_map.get("Subject", "(no subject)"),
            "sender": header_map.get("From", "unknown"),
            "date": header_map.get("Date", "unknown"),
            "snippet": message.get("snippet", ""),
            "body": body[:3000],  # cap at 3000 chars per email
            "labels": message.get("labelIds", []),
        }

    def _extract_body(self, payload: dict) -> str:
        """Extract plain text body from email payload."""
        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            return self._decode_base64(data)

        if "multipart" in mime_type:
            return self._extract_from_parts(payload.get("parts", []))

        return payload.get("body", {}).get("data", "")

    def _extract_from_parts(self, parts: list) -> str:
        """Recursively extract text from multipart email."""
        for part in parts:
            mime = part.get("mimeType", "")
            if mime == "text/plain":
                data = part.get("body", {}).get("data", "")
                text = self._decode_base64(data)
                if text:
                    return text
            elif "multipart" in mime:
                result = self._extract_from_parts(part.get("parts", []))
                if result:
                    return result
        return ""

    def _decode_base64(self, data: str) -> str:
        """Decode base64url encoded email body."""
        if not data:
            return ""
        try:
            padded = data + "=" * (4 - len(data) % 4)
            return base64.urlsafe_b64decode(padded).decode(
                "utf-8", errors="replace"
            )
        except Exception:
            return ""


live_gmail_service = LiveGmailService()