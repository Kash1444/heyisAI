# app/api/auth.py

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.services.gmail_auth_service import gmail_auth_service
from app.schemas.auth import AuthStatus

logger = logging.getLogger(__name__)

# APIRouter is like a mini FastAPI app.
# We register it in main.py with a prefix like /auth
router = APIRouter()


@router.get("/login")
async def login():
    """
    Step 1: Redirect user to Google's OAuth consent screen.

    When user visits /auth/login, we generate the Google URL
    and redirect them there. Google handles the actual login.
    """
    authorization_url, state = gmail_auth_service.get_authorization_url()

    # Store state in session for CSRF validation
    # For now we log it — we'll add proper session storage later
    logger.info(f"Redirecting to Google OAuth. State: {state[:10]}...")

    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def oauth_callback(code: str, state: str):
    """
    Step 2: Google redirects back here with an authorization code.

    After user approves permissions, Google redirects to this URL
    with a 'code' parameter. We exchange that code for tokens.
    """
    try:
        credentials = gmail_auth_service.exchange_code_for_tokens(code)
        logger.info("OAuth callback successful. Tokens stored.")

        # In a real app, redirect to your frontend dashboard.
        # For now, return a success message.
        return {
            "message": "Authentication successful!",
            "authenticated": True,
            "note": "Tokens stored. You can now use the Gmail API."
        }

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get("/status", response_model=AuthStatus)
async def auth_status():
    """
    Check whether the user is currently authenticated.
    Frontend uses this to know whether to show login button.
    """
    is_auth = gmail_auth_service.is_authenticated()

    return AuthStatus(
        authenticated=is_auth,
        message="Authenticated and ready" if is_auth else "Please login at /auth/login"
    )


@router.post("/logout")
async def logout():
    """Revoke tokens and log the user out."""
    gmail_auth_service.revoke_and_logout()
    return {"message": "Logged out successfully"}