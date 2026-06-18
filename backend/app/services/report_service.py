from app.db.supabase_storage import get_db
from app.schemas.report_schema import ProgressReportCreate, ProgressReportUpdate
from app.services.pdf_service import build_report_pdf, save_pdf

TABLE = "progress_report"


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _enrich_report(report: dict) -> dict:
    """Add element_type details to a report dict for PDF generation."""
    et = get_db().table("element_type").select("name, description, color_hex").eq(
        "id", report["element_type_id"]
    ).execute()
    report["element_type"] = et.data[0] if et.data else {"name": "Unknown", "description": None, "color_hex": None}
    return report


def create_progress_report_with_pdf(data: ProgressReportCreate) -> dict:
    insert_result = get_db().table(TABLE).insert({
        "run_id": data.run_id,
        "element_type_id": data.element_type_id,
        "total_elements": data.total_elements,
        "completed": data.completed,
        "partial": data.partial,
        "not_built": data.not_built,
        "completion_pct": data.completion_pct,
        "current_stage": data.current_stage,
        "pdf_path": None,
    }).execute()
    report = insert_result.data[0]
    report = _enrich_report(report)

    pdf_bytes = build_report_pdf(report)
    pdf_url = save_pdf(pdf_bytes, report["run_id"], report["id"])

    updated = get_db().table(TABLE).update({"pdf_path": pdf_url}).eq("id", report["id"]).execute()
    return updated.data[0]


def create_progress_report(data: ProgressReportCreate) -> dict:
    result = get_db().table(TABLE).insert({
        "run_id": data.run_id,
        "element_type_id": data.element_type_id,
        "total_elements": data.total_elements,
        "completed": data.completed,
        "partial": data.partial,
        "not_built": data.not_built,
        "completion_pct": data.completion_pct,
        "current_stage": data.current_stage,
        "pdf_path": data.pdf_path,
    }).execute()
    return result.data[0]


def get_all_progress_reports(skip: int = 0, limit: int = 10) -> list[dict]:
    result = (
        get_db().table(TABLE).select("*")
        .order("generated_at", desc=True)
        .limit(limit).offset(skip)
        .execute()
    )
    return result.data


def get_progress_report_by_id(report_id: str) -> dict | None:
    result = get_db().table(TABLE).select("*").eq("id", report_id).execute()
    return result.data[0] if result.data else None


def update_progress_report(report_id: str, data: ProgressReportUpdate) -> dict | None:
    updates = {}
    if data.run_id is not None:           updates["run_id"] = data.run_id
    if data.element_type_id is not None:  updates["element_type_id"] = data.element_type_id
    if data.total_elements is not None:   updates["total_elements"] = data.total_elements
    if data.completed is not None:        updates["completed"] = data.completed
    if data.partial is not None:          updates["partial"] = data.partial
    if data.not_built is not None:        updates["not_built"] = data.not_built
    if data.completion_pct is not None:   updates["completion_pct"] = data.completion_pct
    if data.current_stage is not None:    updates["current_stage"] = data.current_stage
    if data.pdf_path is not None:         updates["pdf_path"] = data.pdf_path
    if data.csv_path is not None:         updates["csv_path"] = data.csv_path
    if data.generated_at is not None:     updates["generated_at"] = _iso(data.generated_at)

    if not updates:
        return get_progress_report_by_id(report_id)

    result = get_db().table(TABLE).update(updates).eq("id", report_id).execute()
    return result.data[0] if result.data else None


def delete_progress_report(report_id: str) -> bool:
    result = get_db().table(TABLE).delete().eq("id", report_id).execute()
    return len(result.data) > 0


def get_progress_report_with_details(report_id: str) -> dict | None:
    result = (
        get_db().table(TABLE)
        .select("*, element_type(name, description, color_hex)")
        .eq("id", report_id)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    row["element_type"] = row.get("element_type") or {"name": "Unknown", "description": None, "color_hex": None}
    return row


def get_all_progress_reports_with_details(skip: int = 0, limit: int = 10) -> list[dict]:
    result = (
        get_db().table(TABLE)
        .select("*, element_type(name, description, color_hex)")
        .order("generated_at", desc=True)
        .limit(limit).offset(skip)
        .execute()
    )
    for row in result.data:
        row["element_type"] = row.get("element_type") or {"name": "Unknown", "description": None, "color_hex": None}
    return result.data
