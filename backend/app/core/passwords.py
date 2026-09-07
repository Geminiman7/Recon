from typing import Annotated
from pydantic import AfterValidator


def validate_password(value: str) -> str:
    if len(value) < 12:
        raise ValueError("Password must be at least 12 characters.")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes.")
    return value


Password = Annotated[str, AfterValidator(validate_password)]
