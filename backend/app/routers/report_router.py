from fastapi import APIRouter

from app.schemas.report_schema import ReportResponse
from app.services.report_service import get_report_by_run_id

router = APIRouter()


@router.get("/{run_id}", response_model=ReportResponse)
def read_report(run_id: str):
    return get_report_by_run_id(run_id)