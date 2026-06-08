from app.db.database import get_connection
from app.schemas.element_type_schema import (
    ElementTypeCreate,
    ElementTypeResponse,
    ElementTypeUpdate,
)


def row_to_element_type_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "name": row[1],
        "description": row[2],
        "color_hex": row[3],
    }


def create_element_type(data: ElementTypeCreate) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO element_type (name, description, color_hex)
                VALUES (%s, %s, %s)
                RETURNING id, name, description, color_hex;
                """,
                (data.name, data.description, data.color_hex)
            )
            row = cur.fetchone()
            conn.commit()

    return row_to_element_type_dict(row)


def get_all_element_types(skip: int = 0, limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, color_hex
                FROM element_type
                ORDER BY name ASC
                LIMIT %s OFFSET %s;
                """,
                (limit, skip)
            )
            rows = cur.fetchall()

    return [row_to_element_type_dict(row) for row in rows]


def get_element_type_by_id(element_type_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, color_hex
                FROM element_type
                WHERE id = %s;
                """,
                (element_type_id,)
            )
            row = cur.fetchone()

    if row is None:
        return None

    return row_to_element_type_dict(row)


def update_element_type(element_type_id: str, data: ElementTypeUpdate) -> dict | None:
    fields = {}
    if data.name is not None:
        fields["name"] = data.name
    if data.description is not None:
        fields["description"] = data.description
    if data.color_hex is not None:
        fields["color_hex"] = data.color_hex

    if not fields:
        return get_element_type_by_id(element_type_id)

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [element_type_id]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE element_type
                SET {set_clause}
                WHERE id = %s
                RETURNING id, name, description, color_hex;
                """,
                values
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        return None

    return row_to_element_type_dict(row)


def delete_element_type(element_type_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM element_type WHERE id = %s;",
                (element_type_id,)
            )
            conn.commit()
            deleted = cur.rowcount

    return deleted > 0
