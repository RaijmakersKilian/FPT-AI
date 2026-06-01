from fastapi import APIRouter, HTTPException, status

from app.schemas.processing_schema import (
    ProcessingRunCreate,
    ProcessingRunResponse,
    ProcessingRunUpdate,
)
from app.services.processing_service import (
    create_processing_run,
    delete_processing_run,
    get_all_processing_runs,
    get_processing_run_by_id,
    update_processing_run,
)

router = APIRouter()


@router.get("", response_model=list[ProcessingRunResponse])
def read_all_processing_runs(skip: int = 0, limit: int = 10):
    return get_all_processing_runs(skip=skip, limit=limit)


@router.get("/{processing_run_id}", response_model=ProcessingRunResponse)
def read_processing_run(processing_run_id: str):
    result = get_processing_run_by_id(processing_run_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing run not found",
        )
    return result


@router.post("", response_model=ProcessingRunResponse, status_code=status.HTTP_201_CREATED)
def create_new_processing_run(data: ProcessingRunCreate):
    return create_processing_run(data)


@router.patch("/{processing_run_id}", response_model=ProcessingRunResponse)
def patch_processing_run(processing_run_id: str, data: ProcessingRunUpdate):
    result = update_processing_run(processing_run_id, data)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing run not found",
        )
    return result


@router.delete("/{processing_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_processing_run_endpoint(processing_run_id: str):
    deleted = delete_processing_run(processing_run_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing run not found",
        )
