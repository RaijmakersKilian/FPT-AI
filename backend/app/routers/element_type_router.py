from fastapi import APIRouter, HTTPException, status

from app.schemas.element_type_schema import (
    ElementTypeCreate,
    ElementTypeResponse,
    ElementTypeUpdate,
)
from app.services.element_type_service import (
    create_element_type,
    delete_element_type,
    get_all_element_types,
    get_element_type_by_id,
    update_element_type,
)

router = APIRouter()


@router.get("", response_model=list[ElementTypeResponse])
def read_all_element_types(skip: int = 0, limit: int = 10):
    return get_all_element_types(skip=skip, limit=limit)


@router.get("/{element_type_id}", response_model=ElementTypeResponse)
def read_element_type(element_type_id: str):
    result = get_element_type_by_id(element_type_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Element type not found",
        )
    return result


@router.post("", response_model=ElementTypeResponse, status_code=status.HTTP_201_CREATED)
def create_new_element_type(data: ElementTypeCreate):
    return create_element_type(data)


@router.patch("/{element_type_id}", response_model=ElementTypeResponse)
def patch_element_type(element_type_id: str, data: ElementTypeUpdate):
    result = update_element_type(element_type_id, data)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Element type not found",
        )
    return result


@router.delete("/{element_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_element_type_endpoint(element_type_id: str):
    deleted = delete_element_type(element_type_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Element type not found",
        )
