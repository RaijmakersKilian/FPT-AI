from app.db.database import get_connection
from app.schemas.report_schema import (
    ProgressReportCreate,
    ProgressReportResponse,
    ProgressReportUpdate,
)


ALL_COLUMNS = (
    "id, run_id, element_type_id, total_elements, completed, partial, "
    "not_built, completion_pct, current_stage, pdf_path, generated_at"
)


def row_to_progress_report_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "run_id": str(row[1]),
        "element_type_id": str(row[2]),
        "total_elements": row[3],
        "completed": row[4],
        "partial": row[5],
        "not_built": row[6],
        "completion_pct": float(row[7]) if row[7] is not None else None,
        "current_stage": row[8],
        "pdf_path": row[9],
        "generated_at": row[10],
    }


def create_progress_report(data: ProgressReportCreate) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO progress_report
                    (run_id, element_type_id, total_elements, completed, partial,
                     not_built, completion_pct, current_stage, pdf_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {ALL_COLUMNS};
                """,
                (
                    data.run_id,
                    data.element_type_id,
                    data.total_elements,
                    data.completed,
                    data.partial,
                    data.not_built,
                    data.completion_pct,
                    data.current_stage,
                    data.pdf_path,
                )
            )
            row = cur.fetchone()
            conn.commit()

    return row_to_progress_report_dict(row)


def get_all_progress_reports(skip: int = 0, limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {ALL_COLUMNS}
                FROM progress_report
                ORDER BY generated_at DESC
                LIMIT %s OFFSET %s;
                """,
                (limit, skip)
            )
            rows = cur.fetchall()

    return [row_to_progress_report_dict(row) for row in rows]


def get_progress_report_by_id(report_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {ALL_COLUMNS}
                FROM progress_report
                WHERE id = %s;
                """,
                (report_id,)
            )
            row = cur.fetchone()

    if row is None:
        return None

    return row_to_progress_report_dict(row)


def update_progress_report(report_id: str, data: ProgressReportUpdate) -> dict | None:
    fields = {}
    if data.run_id is not None:
        fields["run_id"] = data.run_id
    if data.element_type_id is not None:
        fields["element_type_id"] = data.element_type_id
    if data.total_elements is not None:
        fields["total_elements"] = data.total_elements
    if data.completed is not None:
        fields["completed"] = data.completed
    if data.partial is not None:
        fields["partial"] = data.partial
    if data.not_built is not None:
        fields["not_built"] = data.not_built
    if data.completion_pct is not None:
        fields["completion_pct"] = data.completion_pct
    if data.current_stage is not None:
        fields["current_stage"] = data.current_stage
    if data.pdf_path is not None:
        fields["pdf_path"] = data.pdf_path
    if data.generated_at is not None:
        fields["generated_at"] = data.generated_at

    if not fields:
        return get_progress_report_by_id(report_id)

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [report_id]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE progress_report
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

    return row_to_progress_report_dict(row)


def delete_progress_report(report_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM progress_report WHERE id = %s;",
                (report_id,)
            )
            conn.commit()
            deleted = cur.rowcount

    return deleted > 0
