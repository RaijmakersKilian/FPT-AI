from app.db.database import get_connection
import json
from app.schemas.detected_element_schema import (
    DetectedElementCreate,
    DetectedElementResponse,
    DetectedElementUpdate,
)


ALL_COLUMNS = (
    "id, run_id, element_type_id, frame_id, confidence, "
    "bbox_x1, bbox_y1, bbox_x2, bbox_y2, mask_polygon, "
    "depth_estimate_m, detected_at"
)


def row_to_detected_element_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "run_id": str(row[1]),
        "element_type_id": str(row[2]),
        "frame_id": row[3],
        "confidence": float(row[4]) if row[4] is not None else None,
        "bbox_x1": float(row[5]) if row[5] is not None else None,
        "bbox_y1": float(row[6]) if row[6] is not None else None,
        "bbox_x2": float(row[7]) if row[7] is not None else None,
        "bbox_y2": float(row[8]) if row[8] is not None else None,
        "mask_polygon": row[9],
        "depth_estimate_m": float(row[10]) if row[10] is not None else None,
        "detected_at": row[11],
    }


def _build_set_clause(fields: dict) -> tuple[str, list]:
    set_parts = []
    values = []
    for k, v in fields.items():
        if k == "mask_polygon" and isinstance(v, dict):
            set_parts.append(f"{k} = %s")
            values.append(json.dumps(v))
        else:
            set_parts.append(f"{k} = %s")
            values.append(v)
    return ", ".join(set_parts), values


def create_detected_element(data: DetectedElementCreate) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO detected_element
                    (run_id, element_type_id, frame_id, confidence,
                     bbox_x1, bbox_y1, bbox_x2, bbox_y2, mask_polygon, depth_estimate_m)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {ALL_COLUMNS};
                """,
                (
                    data.run_id,
                    data.element_type_id,
                    data.frame_id,
                    data.confidence,
                    data.bbox_x1,
                    data.bbox_y1,
                    data.bbox_x2,
                    data.bbox_y2,
                    json.dumps(data.mask_polygon) if data.mask_polygon is not None else None,
                    data.depth_estimate_m,
                )
            )
            row = cur.fetchone()
            conn.commit()

    return row_to_detected_element_dict(row)


def get_all_detected_elements(skip: int = 0, limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {ALL_COLUMNS}
                FROM detected_element
                ORDER BY detected_at DESC
                LIMIT %s OFFSET %s;
                """,
                (limit, skip)
            )
            rows = cur.fetchall()

    return [row_to_detected_element_dict(row) for row in rows]


def get_detected_element_by_id(element_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {ALL_COLUMNS}
                FROM detected_element
                WHERE id = %s;
                """,
                (element_id,)
            )
            row = cur.fetchone()

    if row is None:
        return None

    return row_to_detected_element_dict(row)


def update_detected_element(element_id: str, data: DetectedElementUpdate) -> dict | None:
    fields = {}
    if data.run_id is not None:
        fields["run_id"] = data.run_id
    if data.element_type_id is not None:
        fields["element_type_id"] = data.element_type_id
    if data.frame_id is not None:
        fields["frame_id"] = data.frame_id
    if data.confidence is not None:
        fields["confidence"] = data.confidence
    if data.bbox_x1 is not None:
        fields["bbox_x1"] = data.bbox_x1
    if data.bbox_y1 is not None:
        fields["bbox_y1"] = data.bbox_y1
    if data.bbox_x2 is not None:
        fields["bbox_x2"] = data.bbox_x2
    if data.bbox_y2 is not None:
        fields["bbox_y2"] = data.bbox_y2
    if data.mask_polygon is not None:
        fields["mask_polygon"] = data.mask_polygon
    if data.depth_estimate_m is not None:
        fields["depth_estimate_m"] = data.depth_estimate_m
    if data.detected_at is not None:
        fields["detected_at"] = data.detected_at

    if not fields:
        return get_detected_element_by_id(element_id)

    set_clause, values = _build_set_clause(fields)
    values.append(element_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE detected_element
                SET {set_clause}
                WHERE id = %s
                RETURNING {ALL_COLUMNS};
                """,
                values
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        return None

    return row_to_detected_element_dict(row)


def delete_detected_element(element_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM detected_element WHERE id = %s;",
                (element_id,)
            )
            conn.commit()
            deleted = cur.rowcount

    return deleted > 0
