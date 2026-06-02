from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.app_usage import AppUsageSyncRequest, AppUsageSyncResponse
from app.services.app_usage_sync_service import sync_app_usage

router = APIRouter(
    prefix="/sync",
    tags=["sync"]
)


@router.post("/app-usage", response_model=AppUsageSyncResponse)
def sync_app_usage_events(
    payload: AppUsageSyncRequest,
    db: Session = Depends(get_db)
):
    result = sync_app_usage(db, payload)
    return AppUsageSyncResponse(success=True, inserted_count=result["inserted"])
