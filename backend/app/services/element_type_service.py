from app.db.supabase_storage import get_db
from app.schemas.element_type_schema import ElementTypeCreate, ElementTypeUpdate

TABLE = "element_type"


def create_element_type(data: ElementTypeCreate) -> dict:
    result = get_db().table(TABLE).insert({
        "name": data.name,
        "description": data.description,
        "color_hex": data.color_hex,
    }).execute()
    return result.data[0]


def get_all_element_types(skip: int = 0, limit: int = 10) -> list[dict]:
    result = get_db().table(TABLE).select("*").order("name").limit(limit).offset(skip).execute()
    return result.data


def get_element_type_by_id(element_type_id: str) -> dict | None:
    result = get_db().table(TABLE).select("*").eq("id", element_type_id).execute()
    return result.data[0] if result.data else None


def update_element_type(element_type_id: str, data: ElementTypeUpdate) -> dict | None:
    updates = {}
    if data.name is not None:        updates["name"] = data.name
    if data.description is not None: updates["description"] = data.description
    if data.color_hex is not None:   updates["color_hex"] = data.color_hex

    if not updates:
        return get_element_type_by_id(element_type_id)

    result = get_db().table(TABLE).update(updates).eq("id", element_type_id).execute()
    return result.data[0] if result.data else None


def delete_element_type(element_type_id: str) -> bool:
    result = get_db().table(TABLE).delete().eq("id", element_type_id).execute()
    return len(result.data) > 0
