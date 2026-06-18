from app.db.supabase_storage import get_db
from app.schemas.detected_element_schema import DetectedElementCreate, DetectedElementUpdate

TABLE = "detected_element"


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def create_detected_element(data: DetectedElementCreate) -> dict:
    result = get_db().table(TABLE).insert({
        "run_id": data.run_id,
        "element_type_id": data.element_type_id,
        "frame_id": data.frame_id,
        "confidence": data.confidence,
        "bbox_x1": data.bbox_x1,
        "bbox_y1": data.bbox_y1,
        "bbox_x2": data.bbox_x2,
        "bbox_y2": data.bbox_y2,
        "mask_polygon": data.mask_polygon,
        "depth_estimate_m": data.depth_estimate_m,
    }).execute()
    return result.data[0]


def get_all_detected_elements(skip: int = 0, limit: int = 10) -> list[dict]:
    result = (
        get_db().table(TABLE).select("*")
        .order("detected_at", desc=True)
        .limit(limit).offset(skip)
        .execute()
    )
    return result.data


def get_detected_element_by_id(element_id: str) -> dict | None:
    result = get_db().table(TABLE).select("*").eq("id", element_id).execute()
    return result.data[0] if result.data else None


def update_detected_element(element_id: str, data: DetectedElementUpdate) -> dict | None:
    updates = {}
    if data.run_id is not None:           updates["run_id"] = data.run_id
    if data.element_type_id is not None:  updates["element_type_id"] = data.element_type_id
    if data.frame_id is not None:         updates["frame_id"] = data.frame_id
    if data.confidence is not None:       updates["confidence"] = data.confidence
    if data.bbox_x1 is not None:          updates["bbox_x1"] = data.bbox_x1
    if data.bbox_y1 is not None:          updates["bbox_y1"] = data.bbox_y1
    if data.bbox_x2 is not None:          updates["bbox_x2"] = data.bbox_x2
    if data.bbox_y2 is not None:          updates["bbox_y2"] = data.bbox_y2
    if data.mask_polygon is not None:     updates["mask_polygon"] = data.mask_polygon
    if data.depth_estimate_m is not None: updates["depth_estimate_m"] = data.depth_estimate_m
    if data.detected_at is not None:      updates["detected_at"] = _iso(data.detected_at)

    if not updates:
        return get_detected_element_by_id(element_id)

    result = get_db().table(TABLE).update(updates).eq("id", element_id).execute()
    return result.data[0] if result.data else None


def delete_detected_element(element_id: str) -> bool:
    result = get_db().table(TABLE).delete().eq("id", element_id).execute()
    return len(result.data) > 0
