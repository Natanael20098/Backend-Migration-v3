from typing import Generic, List, TypeVar
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base Pydantic model that serializes fields to camelCase aliases.
    Matches Java Jackson default serialization for API response compatibility."""
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


class PageResponse(CamelModel, Generic[T]):
    """Matches the Spring Data Page response shape expected by the frontend."""
    content: List[T]
    total_elements: int
    total_pages: int
    size: int
    number: int


class ErrorResponse(BaseModel):
    """Standard domain error response. Use 'message' key per api-compatibility-rules.md."""
    message: str


class AuthErrorResponse(BaseModel):
    """Auth-specific error response. Uses 'error' key to match Java AuthController exactly."""
    error: str
