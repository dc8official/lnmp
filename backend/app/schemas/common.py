from __future__ import annotations
from typing import Generic, Literal, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class ErrorDetail(BaseModel):
    code: str
    message: str

class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int

class APIResponse(BaseModel, Generic[T]):
    status: Literal["success", "error"]
    data: Optional[T] = None
    meta: Optional[PaginationMeta] = None
    error: Optional[ErrorDetail] = None

    @classmethod
    def success(cls, data: T, meta: Optional[PaginationMeta] = None):
        return cls(status="success", data=data, meta=meta)

    @classmethod
    def error(cls, code: str, message: str):
        return cls(
            status="error",
            error=ErrorDetail(code=code, message=message)
        )
