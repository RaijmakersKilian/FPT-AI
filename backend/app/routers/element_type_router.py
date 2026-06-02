from fastapi import APIRouter

from app.schemas.element_type_schema import ElementTypeResponse, ElementTypeCreate
from app.services.element_type_service import (
    create_element_type,     
    get_all_element_types,   
    get_element_type_by_id,
)

router = APIRouter()


@router.get("", response_model=list[ElementTypeResponse])
def read_all_element_types(skip: int = 0, limit: int = 10):
    return get_all_element_types(skip=skip, limit=limit)

@router.get("/{element_type_id}", response_model=ElementTypeResponse)
def read_element_type(element_type_id: str):
    return get_element_type_by_id(element_type_id)

@router.post("", response_model=ElementTypeResponse)
def create_new_element_type(element_type_data: ElementTypeCreate):
    return create_element_type(element_type_data)


