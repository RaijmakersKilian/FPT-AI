from pydantic import BaseModel, Field


class ElementTypeCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None


class ElementTypeResponse(BaseModel):
    id: str
    name: str
    description: str | None = None