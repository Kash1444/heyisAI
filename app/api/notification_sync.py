from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.notification import NotificationSyncRequest, NotificationSyncResponse
from app.services.notification_sync_service import sync_notifications

router = APIRouter(
    prefix="/sync",
    tags=["sync"]
)


@router.post("/notifications", response_model=NotificationSyncResponse)
def sync_device_notifications(
    payload: NotificationSyncRequest,
    db: Session = Depends(get_db)
):
    result = sync_notifications(db, payload)
    return NotificationSyncResponse(success=True, inserted_count=result["inserted"])
