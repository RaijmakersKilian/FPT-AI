from fastapi import APIRouter, HTTPException, status

from app.schemas.report_schema import (
    ProgressReportCreate,
    ProgressReportResponse,
    ProgressReportUpdate,
)
from app.services.report_service import (
    create_progress_report,
    delete_progress_report,
    get_all_progress_reports,
    get_progress_report_by_id,
    update_progress_report,
)

router = APIRouter()


@router.get("", response_model=list[ProgressReportResponse])
def read_all_progress_reports(skip: int = 0, limit: int = 10):
    return get_all_progress_reports(skip=skip, limit=limit)


@router.get("/{report_id}", response_model=ProgressReportResponse)
def read_progress_report(report_id: str):
    result = get_progress_report_by_id(report_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress report not found",
        )
    return result


@router.post("", response_model=ProgressReportResponse, status_code=status.HTTP_201_CREATED)
def create_new_progress_report(data: ProgressReportCreate):
    return create_progress_report(data)


@router.patch("/{report_id}", response_model=ProgressReportResponse)
def patch_progress_report(report_id: str, data: ProgressReportUpdate):
    result = update_progress_report(report_id, data)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress report not found",
        )
    return result


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_progress_report_endpoint(report_id: str):
    deleted = delete_progress_report(report_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress report not found",
        )
