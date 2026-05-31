# app/services/gmail_auth_service.py

import json
import logging
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Gmail Scopes ───────────────────────────────────────────────────────────
# Scopes define exactly what permissions we ask the user for.
# We only ask for what we need — this is least privilege principle.
# readonly = we can read emails but never send, delete, or modify.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]

# Where we store the token locally.
# In production this would be a database row per user.
# For Phase 1, a local file per user is fine.
TOKEN_FILE = Path("token.json")


class GmailAuthService:
    """
    Handles the complete Gmail OAuth 2.0 lifecycle:
    - Generating the authorization URL (step 1)
    - Exchanging the code for tokens (step 2)
    - Storing tokens securely (step 3)
    - Refreshing expired tokens automatically (step 4)
    - Providing valid credentials to other services (step 5)
    """

    def __init__(self):
        # Build the client config dict from our settings.
        # This is what google's OAuth library expects.
        self.client_config = {
            "web": {
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "redirect_uris": [settings.gmail_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    def get_valid_credentials(self):
        """
        Returns valid credentials, refreshing if expired.
        Saves refreshed token immediately so next call is fast.
        """
        if not TOKEN_FILE.exists():
            logger.warning("No token file found. User must authenticate.")
            return None

        credentials = self._load_tokens()

        if not credentials:
            return None

        if credentials.expired and credentials.refresh_token:
            logger.info("Access token expired. Refreshing...")

            try:
                credentials.refresh(Request())

                # Save refreshed token immediately
                self._save_tokens(credentials)

                logger.info(
                    "Token refreshed and saved successfully"
                )

            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return None

        return credentials

    def exchange_code_for_tokens(self, code: str) -> Credentials:
        """
        Step 2 of OAuth: Exchange the authorization code for tokens.

        Google gives us a short-lived 'code' in the callback URL.
        We exchange it for actual access_token + refresh_token.
        This exchange happens server-side — the tokens never
        touch the browser.
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=GMAIL_SCOPES,
            redirect_uri=settings.gmail_redirect_uri,
        )

        # This makes a POST request to Google's token endpoint
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Save tokens to disk for reuse
        self._save_tokens(credentials)

        logger.info("Successfully exchanged code for tokens")
        return credentials

    def get_valid_credentials(self) -> Optional[Credentials]:
        """
        Returns valid credentials, refreshing if expired.

        This is what every other service calls when they need
        to make a Gmail API request. They don't manage tokens
        themselves — they ask this service for valid credentials.

        This is the Single Responsibility Principle:
        only this service knows about tokens and auth.
        """
        if not TOKEN_FILE.exists():
            logger.warning("No token file found. User must authenticate.")
            return None

        credentials = self._load_tokens()

        if not credentials:
            return None

        # If token is expired but we have a refresh token,
        # refresh it automatically. User stays logged in.
        if credentials.expired and credentials.refresh_token:
            logger.info("Access token expired. Refreshing...")
            credentials.refresh(Request())
            self._save_tokens(credentials)
            logger.info("Token refreshed successfully")

        return credentials

    def is_authenticated(self) -> bool:
        """Quick check — is there a valid token available?"""
        credentials = self.get_valid_credentials()
        return credentials is not None and credentials.valid

    def revoke_and_logout(self):
        """
        Logout: delete stored tokens.
        In production you'd also call Google's revoke endpoint.
        """
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            logger.info("Tokens deleted. User logged out.")

    # ── Private Helpers ────────────────────────────────────────────────────

    def _save_tokens(self, credentials: Credentials):
        """
        Persist tokens to disk.

        We serialize the credentials object to JSON.
        In production, this would encrypt the tokens
        and store them in a database keyed by user ID.
        """
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }

        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f, indent=2)

        logger.debug(f"Tokens saved to {TOKEN_FILE}")

    def _load_tokens(self) -> Optional[Credentials]:
        """Load tokens from disk and reconstruct Credentials object."""
        try:
            with open(TOKEN_FILE, "r") as f:
                token_data = json.load(f)

            credentials = Credentials(
                token=token_data["token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data["token_uri"],
                client_id=token_data["client_id"],
                client_secret=token_data["client_secret"],
                scopes=token_data.get("scopes", []),
            )

            return credentials

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load tokens: {e}")
            return None


# Singleton — one instance shared across the app
gmail_auth_service = GmailAuthService()