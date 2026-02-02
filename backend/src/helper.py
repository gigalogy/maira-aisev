def enum_error(enum_cls, field_name: str):
    allowed = ", ".join(e.value for e in enum_cls)
    return ValueError(f"{field_name} must be one of: {allowed}")
