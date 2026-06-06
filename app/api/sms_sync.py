from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.sms import SmsSyncRequest, SmsSyncResponse
from app.services.sms_sync_service import sync_sms
from app.services.sms_enricher import enrich_pending_sms_task

router = APIRouter()


@router.post("/sms", response_model=SmsSyncResponse)
def sync_sms_messages(
    payload: SmsSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    result = sync_sms(db, payload)
    if result["inserted"] > 0:
        background_tasks.add_task(enrich_pending_sms_task)
    return SmsSyncResponse(success=True, inserted_count=result["inserted"])

