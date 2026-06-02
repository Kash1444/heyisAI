from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db

from app.schemas.call_log import (
    CallSyncRequest,
    CallSyncResponse
)

from app.services.call_sync_service import sync_calls

router = APIRouter()


@router.post(
    "/calls",
    response_model=CallSyncResponse)

def sync_call_logs(
    payload: CallSyncRequest,
    db: Session = Depends(get_db)):

    sync_result = sync_calls(db, payload)

    return CallSyncResponse(
        success=True,
        inserted_count=sync_result["inserted"]
    )