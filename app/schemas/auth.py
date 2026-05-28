# app/schemas/auth.py

from pydantic import BaseModel
from typing import Optional


class TokenData(BaseModel):
    """
    Represents the OAuth tokens returned by Google.
    This is what we store after a successful login.
    """
    access_token: str
    refresh_token: Optional[str] = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    scopes: list[str] = []


class UserInfo(BaseModel):
    """
    Basic profile info we get from Google after login.
    """
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None


class AuthStatus(BaseModel):
    """
    Response we send back to the client about auth state.
    """
    authenticated: bool
    email: Optional[str] = None
    message: str
