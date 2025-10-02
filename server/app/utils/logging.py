import json
import logging
import uuid
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


REQUEST_ID_CTX = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Attach the request ID from the context var to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID_CTX.get()
        return True


class JsonFormatter(logging.Formatter):
    """Formatter that renders log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - exercised via tests
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            log_payload["request_id"] = request_id

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and key not in log_payload:
                log_payload[key] = value

        return json.dumps(log_payload, default=str)


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure root logging to emit structured JSON to stdout."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    logging.basicConfig(level=level, handlers=[handler], force=True)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Populate request IDs and emit structured request logs."""

    def __init__(self, app, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self.header_name = header_name
        self._logger = logging.getLogger("app.request")

    async def dispatch(self, request, call_next):  # pragma: no cover - integration tested
        request_id = request.headers.get(self.header_name) or uuid.uuid4().hex
        token = REQUEST_ID_CTX.set(request_id)
        start = time.time()
        self._logger.info(
            "request_started",
            extra={"method": request.method, "path": request.url.path},
        )

        try:
            response = await call_next(request)
        except HTTPException as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._logger.warning(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": exc.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
            for header_name, header_value in (exc.headers or {}).items():
                response.headers[header_name] = header_value
        except Exception:
            duration_ms = int((time.time() - start) * 1000)
            self._logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
        else:
            duration_ms = int((time.time() - start) * 1000)
            self._logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        finally:
            REQUEST_ID_CTX.reset(token)

        response.headers[self.header_name] = request_id
        return response
