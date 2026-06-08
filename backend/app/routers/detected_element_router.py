from fastapi import APIRouter, HTTPException, status

from app.schemas.detected_element_schema import (
    DetectedElementCreate,
    DetectedElementResponse,
    DetectedElementUpdate,
)
from app.services.detected_element_service import (
    create_detected_element,
    delete_detected_element,
    get_all_detected_elements,
    get_detected_element_by_id,
    update_detected_element,
)

router = APIRouter()


@router.get("", response_model=list[DetectedElementResponse])
def read_all_detected_elements(skip: int = 0, limit: int = 10):
    return get_all_detected_elements(skip=skip, limit=limit)


@router.get("/{element_id}", response_model=DetectedElementResponse)
def read_detected_element(element_id: str):
    result = get_detected_element_by_id(element_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detected element not found",
        )
    return result


@router.post("", response_model=DetectedElementResponse, status_code=status.HTTP_201_CREATED)
def create_new_detected_element(data: DetectedElementCreate):
    return create_detected_element(data)


@router.patch("/{element_id}", response_model=DetectedElementResponse)
def patch_detected_element(element_id: str, data: DetectedElementUpdate):
    result = update_detected_element(element_id, data)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detected element not found",
        )
    return result


@router.delete("/{element_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_detected_element_endpoint(element_id: str):
    deleted = delete_detected_element(element_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detected element not found",
        )
