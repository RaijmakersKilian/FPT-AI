from app.db.supabase_storage import get_db
from app.schemas.processing_schema import ProcessingRunCreate, ProcessingRunUpdate

TABLE = "processing_run"


def _iso(v):
    """Convert datetime to ISO string for Supabase REST."""
    return v.isoformat() if hasattr(v, "isoformat") else v


def create_processing_run(data: ProcessingRunCreate) -> dict:
    result = get_db().table(TABLE).insert({
        "video_id": data.video_id,
        "element_type_id": data.element_type_id,
    }).execute()
    return result.data[0]


def get_all_processing_runs(skip: int = 0, limit: int = 10) -> list[dict]:
    result = (
        get_db().table(TABLE).select("*")
        .order("started_at", desc=True)
        .limit(limit).offset(skip)
        .execute()
    )
    return result.data


def get_processing_run_by_id(processing_run_id: str) -> dict | None:
    result = get_db().table(TABLE).select("*").eq("id", processing_run_id).execute()
    return result.data[0] if result.data else None


def update_processing_run(processing_run_id: str, data: ProcessingRunUpdate) -> dict | None:
    updates = {}
    if data.element_type_id is not None:  updates["element_type_id"] = data.element_type_id
    if data.started_at is not None:       updates["started_at"] = _iso(data.started_at)
    if data.completed_at is not None:     updates["completed_at"] = _iso(data.completed_at)
    if data.status is not None:           updates["status"] = data.status
    if data.frames_extracted is not None: updates["frames_extracted"] = data.frames_extracted
    if data.pointcloud_path is not None:  updates["pointcloud_path"] = data.pointcloud_path
    if data.detections_path is not None:  updates["detections_path"] = data.detections_path
    if data.bim_model_path is not None:   updates["bim_model_path"] = data.bim_model_path

    if not updates:
        return get_processing_run_by_id(processing_run_id)

    result = get_db().table(TABLE).update(updates).eq("id", processing_run_id).execute()
    return result.data[0] if result.data else None


def delete_processing_run(processing_run_id: str) -> bool:
    result = get_db().table(TABLE).delete().eq("id", processing_run_id).execute()
    return len(result.data) > 0
