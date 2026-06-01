from fastapi import APIRouter, HTTPException, status

from app.schemas.processing_schema import (
    ProcessingRunCreate,
    ProcessingRunResponse,
    ProcessingStatusResponse
)
from app.services.processing_service import (
    start_processing,
    get_processing_status
)

router = APIRouter()


@router.post(
    "",
    response_model=ProcessingRunResponse,
    status_code=status.HTTP_201_CREATED
)
def create_processing_run(payload: ProcessingRunCreate):
    return start_processing(payload)


@router.get("/{run_id}/status", response_model=ProcessingStatusResponse)
def read_processing_status(run_id: str):
    run_status = get_processing_status(run_id)

    if run_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing run not found"
        )

    return run_status