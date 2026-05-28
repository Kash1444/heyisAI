# app/schemas/email.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EmailMetadata(BaseModel):
    """
    Lightweight email object — just the important fields.
    We use this for search results and listings.
    No body content here — keeps responses fast.
    """
    id: str
    thread_id: str
    subject: str
    sender: str
    recipient: str
    date: str
    snippet: str
    labels: list[str] = []


class EmailFull(EmailMetadata):
    """
    Full email including decoded body.
    We use this when user wants to read a specific email.
    Inherits all fields from EmailMetadata.
    """
    body_text: str = ""      # plain text version
    body_html: str = ""      # html version (optional)


class EmailSearchResult(BaseModel):
    """
    What we return when user searches emails.
    Contains results + metadata about the search.
    """
    query: str
    total_found: int
    emails: list[EmailMetadata]


class EmailIngestionStats(BaseModel):
    """
    Stats returned after ingesting emails into vector DB.
    """
    total_fetched: int
    total_embedded: int
    total_failed: int
    message: str