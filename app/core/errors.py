from __future__ import annotations

import logging
from collections.abc import Iterable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.error import ApiErrorDetail, ApiErrorResponse


logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: Iterable[ApiErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = list(details or [])


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiErrorResponse(detail=exc.message).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "loc": list(item.get("loc", ())),
                "msg": str(item.get("msg") or "Entrada invalida"),
                "type": str(item.get("type") or "value_error"),
            }
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=ApiErrorResponse(detail=details).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
        response = _build_error_response(
            detail="Erro interno inesperado",
        )
        return JSONResponse(status_code=500, content=response.model_dump())


def _build_error_response(*, detail: str) -> ApiErrorResponse:
    return ApiErrorResponse(detail=detail)
