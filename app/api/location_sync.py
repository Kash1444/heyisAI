# DESIGN PLACEHOLDER — full implementation deferred to a future phase.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.location import LocationSyncRequest, LocationSyncResponse
from app.services.location_sync_service import sync_location

router = APIRouter(
    prefix="/sync",
    tags=["sync"]
)


@router.post("/location", response_model=LocationSyncResponse)
def sync_location_history(
    payload: LocationSyncRequest,
    db: Session = Depends(get_db)
):
    result = sync_location(db, payload)
    return LocationSyncResponse(success=True, inserted_count=result["inserted"])
