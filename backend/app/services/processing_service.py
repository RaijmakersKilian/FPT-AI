from app.db.database import get_connection
from app.schemas.processing_schema import (
    ProcessingRunCreate,
    ProcessingRunResponse,
    ProcessingRunUpdate,
)


def row_to_processing_run_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "video_id": str(row[1]),
        "element_type_id": str(row[2]) if row[2] else None,
        "started_at": row[3],
        "completed_at": row[4],
        "status": row[5],
        "frames_extracted": row[6],
        "pointcloud_path": row[7],
        "detections_path": row[8],
        "bim_model_path": row[9],
    }


def create_processing_run(data: ProcessingRunCreate) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO processing_run (video_id, element_type_id)
                VALUES (%s, %s)
                RETURNING id, video_id, element_type_id, started_at, completed_at,
                          status, frames_extracted, pointcloud_path,
                          detections_path, bim_model_path;
                """,
                (data.video_id, data.element_type_id)
            )
            row = cur.fetchone()
            conn.commit()

    return row_to_processing_run_dict(row)


def get_all_processing_runs(skip: int = 0, limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, video_id, element_type_id, started_at, completed_at,
                       status, frames_extracted, pointcloud_path,
                       detections_path, bim_model_path
                FROM processing_run
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s;
                """,
                (limit, skip)
            )
            rows = cur.fetchall()

    return [row_to_processing_run_dict(row) for row in rows]


def get_processing_run_by_id(processing_run_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, video_id, element_type_id, started_at, completed_at,
                       status, frames_extracted, pointcloud_path,
                       detections_path, bim_model_path
                FROM processing_run
                WHERE id = %s;
                """,
                (processing_run_id,)
            )
            row = cur.fetchone()

    if row is None:
        return None

    return row_to_processing_run_dict(row)


def update_processing_run(processing_run_id: str, data: ProcessingRunUpdate) -> dict | None:
    fields = {}
    if data.element_type_id is not None:
        fields["element_type_id"] = data.element_type_id
    if data.started_at is not None:
        fields["started_at"] = data.started_at
    if data.completed_at is not None:
        fields["completed_at"] = data.completed_at
    if data.status is not None:
        fields["status"] = data.status
    if data.frames_extracted is not None:
        fields["frames_extracted"] = data.frames_extracted
    if data.pointcloud_path is not None:
        fields["pointcloud_path"] = data.pointcloud_path
    if data.detections_path is not None:
        fields["detections_path"] = data.detections_path
    if data.bim_model_path is not None:
        fields["bim_model_path"] = data.bim_model_path

    if not fields:
        return get_processing_run_by_id(processing_run_id)

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [processing_run_id]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE processing_run
                SET {set_clause}
                WHERE id = %s
                RETURNING id, video_id, element_type_id, started_at, completed_at,
                          status, frames_extracted, pointcloud_path,
                          detections_path, bim_model_path;
                """,
                values
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        return None

    return row_to_processing_run_dict(row)


def delete_processing_run(processing_run_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM processing_run WHERE id = %s;",
                (processing_run_id,)
            )
            conn.commit()
            deleted = cur.rowcount

    return deleted > 0
