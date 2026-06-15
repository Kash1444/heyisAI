# app/services/live_gmail_service.py

import asyncio
from concurrent.futures import ThreadPoolExecutor

import base64
import logging
from typing import Optional

from googleapiclient.discovery import build
from app.services.gmail_auth_service import gmail_auth_service

logger = logging.getLogger(__name__)


class LiveGmailService:
    """
    Searches and fetches emails directly from Gmail API.
    No pre-ingestion. No ChromaDB.
    """

    def _get_client(self):
        credentials = gmail_auth_service.get_valid_credentials()
        if not credentials:
            raise ValueError("Not authenticated. Visit /auth/login")
        return build("gmail", "v1", credentials=credentials)

    # ------------------------------------------------------------
    # MAIN SEARCH ENTRY
    # ------------------------------------------------------------

    def search_and_fetch(
        self,
        queries: list[str],
        max_per_query: int = 10,
    ) -> list[dict]:

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

    # ------------------------------------------------------------
    # UPDATED FUNCTION (YOUR REQUEST)
    # ------------------------------------------------------------

    def _search_one_query(self, query: str, max_results: int) -> list[dict]:
        """Search Gmail and fetch all emails concurrently."""

        # Pre-refresh token ONCE in main thread before spawning workers
        # This prevents every thread from hitting 401 and refreshing independently
        credentials = gmail_auth_service.get_valid_credentials()
        if not credentials:
            raise ValueError("Not authenticated")

        # Force refresh if expired so threads get a valid token
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            gmail_auth_service._save_tokens(credentials)
            logger.info("Pre-refreshed token before concurrent fetch")

        # Step 1: List message IDs
        service = build("gmail", "v1", credentials=credentials)
        result = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
        ).execute()

        messages = result.get("messages", [])
        if not messages:
            return []

        logger.info(f"Query '{query}' → {len(messages)} messages")

        # Step 2: Fetch concurrently with max 3 workers
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(self._fetch_email_with_own_client, msg["id"])
                for msg in messages
            ]
            emails = []
            for future in futures:
                try:
                    result = future.result(timeout=8)
                    if result:
                        emails.append(result)
                except Exception as e:
                    logger.warning(f"Thread fetch failed: {e}")
                    continue

        return emails
        
    # ------------------------------------------------------------
    # THREAD-SAFE FETCH (NEW CLIENT PER THREAD)
    # ------------------------------------------------------------

    def _fetch_email_with_own_client(self, email_id: str) -> Optional[dict]:
        """
        Fetch one email using a fresh Gmail client per thread.

        Important:
        - googleapiclient is NOT thread-safe
        - Each thread must create its own client
        """

        try:
            credentials = gmail_auth_service.get_valid_credentials()
            if not credentials:
                return None

            thread_service = build("gmail", "v1", credentials=credentials)

            message = thread_service.users().messages().get(
                userId="me",
                id=email_id,
                format="full",
            ).execute()

            return self._parse_email(message)

        except Exception as e:
            logger.warning(f"Failed to fetch email {email_id}: {e}")
            return None

    # ------------------------------------------------------------
    # PARSING
    # ------------------------------------------------------------

    def _parse_email(self, message: dict) -> dict:
        payload = message.get("payload", {})
        headers = payload.get("headers", [])

        header_map = {h["name"]: h["value"] for h in headers}

        body = self._extract_body(payload)

        return {
            "id": message["id"],
            "thread_id": message["threadId"],
            "subject": header_map.get("Subject", "(no subject)"),
            "sender": header_map.get("From", "unknown"),
            "date": header_map.get("Date", "unknown"),
            "snippet": message.get("snippet", ""),
            "body": body[:3000],
            "labels": message.get("labelIds", []),
        }

    # ------------------------------------------------------------
    # BODY EXTRACTION
    # ------------------------------------------------------------

    def _extract_body(self, payload: dict) -> str:
        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            return self._decode_base64(data)

        if "multipart" in mime_type:
            return self._extract_from_parts(payload.get("parts", []))

        return payload.get("body", {}).get("data", "")

    def _extract_from_parts(self, parts: list) -> str:
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
        if not data:
            return ""

        try:
            padded = data + "=" * (4 - len(data) % 4)
            return base64.urlsafe_b64decode(padded).decode(
                "utf-8", errors="replace"
            )
        except Exception:
            return ""


# Singleton instance
live_gmail_service = LiveGmailService()