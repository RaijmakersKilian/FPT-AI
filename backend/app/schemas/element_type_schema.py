import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


def validate_color_hex(v: str | None) -> str | None:
    if v is None:
        return None
    if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
        raise ValueError("must be a valid hex color like #FF5733")
    return v


class ElementTypeCreate(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    description: str | None = None
    color_hex: str | None = None

    _validate_color: classmethod = field_validator("color_hex")(validate_color_hex)


class ElementTypeUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1)] | None = None
    description: str | None = None
    color_hex: str | None = None

    _validate_color: classmethod = field_validator("color_hex")(validate_color_hex)


class ElementTypeResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    color_hex: str | None = None
