from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request


REQUEST_ID_HEADER = "x-request-id"
APP_LOGGER_NAME = "app"
HTTP_LOGGER_NAME = "app.http"


_RESERVED_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    app_logger.setLevel(_coerce_log_level(level))

    if not any(getattr(handler, "_bestchoice_json_handler", False) for handler in app_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        handler._bestchoice_json_handler = True  # type: ignore[attr-defined]
        app_logger.addHandler(handler)

    app_logger.propagate = False


def register_request_logging_middleware(app: FastAPI) -> None:
    http_logger = logging.getLogger(HTTP_LOGGER_NAME)

    @app.middleware("http")
    async def log_http_request(request: Request, call_next):
        started_at = time.perf_counter()
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = _elapsed_ms(started_at)
            http_logger.exception(
                "http_request_failed",
                extra=_request_log_extra(
                    request=request,
                    request_id=request_id,
                    event="http_request_failed",
                    status_code=500,
                    duration_ms=duration_ms,
                ),
            )
            raise

        response.headers[REQUEST_ID_HEADER] = request_id
        duration_ms = _elapsed_ms(started_at)
        log_method = http_logger.error if response.status_code >= 500 else http_logger.info
        log_method(
            "http_request",
            extra=_request_log_extra(
                request=request,
                request_id=request_id,
                event="http_request",
                status_code=response.status_code,
                duration_ms=duration_ms,
            ),
        )
        return response


def _request_log_extra(
    *,
    request: Request,
    request_id: str,
    event: str,
    status_code: int,
    duration_ms: float,
) -> dict[str, Any]:
    return {
        "event": event,
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _coerce_log_level(level: str) -> int:
    resolved_level = getattr(logging, level.strip().upper(), logging.INFO)
    return resolved_level if isinstance(resolved_level, int) else logging.INFO
