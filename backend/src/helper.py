from typing import Optional
from uuid import UUID
from fastapi import HTTPException


def enum_error(enum_cls, field_name: str):
    allowed = ", ".join(e.value for e in enum_cls)
    return ValueError(f"{field_name} must be one of: {allowed}")


def validate_uuid(value: Optional[str], name: str) -> Optional[str]:
    if value is None:
        return None
    try:
        UUID(value)  # validates
        return value
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{name} must be a valid UUID")
