from uuid import uuid4

from app.schemas.element_type_schema import ElementTypeCreate


element_types_db = [
    {
        "id": "element_type_001",
        "name": "Beam",
        "description": "Sample beam element"
    },
    {
        "id": "element_type_002",
        "name": "Column",
        "description": "Sample column element"
    }
]


def get_all_element_types(skip: int = 0, limit: int = 10):
    return element_types_db[skip: skip + limit]


def get_element_type_by_id(element_type_id: str):
    for element_type in element_types_db:
        if element_type["id"] == element_type_id:
            return element_type

    return None


def create_element_type(element_type_data: ElementTypeCreate):
    new_element_type = {
        "id": str(uuid4()),
        "name": element_type_data.name,
        "description": element_type_data.description
    }

    element_types_db.append(new_element_type)

    return new_element_type