from __future__ import annotations

from pydantic import BaseModel


class ApiErrorDetail(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ApiErrorResponse(BaseModel):
    detail: str | list[ApiErrorDetail]
