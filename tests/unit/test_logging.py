import json
import logging
import pathlib
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "server"))

from app.utils.logging import REQUEST_ID_CTX, RequestIdMiddleware, configure_logging


def build_app():
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/echo")
    def echo():
        return {"request_id": REQUEST_ID_CTX.get()}

    return app


def test_request_id_propagates_from_header():
    app = build_app()
    client = TestClient(app)

    response = client.get("/echo", headers={"X-Request-ID": "custom-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "custom-id"
    assert response.json()["request_id"] == "custom-id"


def test_request_id_is_generated_when_missing():
    app = build_app()
    client = TestClient(app)

    response = client.get("/echo")

    assert response.status_code == 200
    generated_id = response.headers["X-Request-ID"]
    assert isinstance(generated_id, str)
    assert len(generated_id) == 32
    assert response.json()["request_id"] == generated_id


def test_structured_logging_includes_request_id(capfd):
    configure_logging()
    capfd.readouterr()

    token = REQUEST_ID_CTX.set("req-123")
    try:
        logging.getLogger("test.logger").info("hello", extra={"foo": "bar"})
    finally:
        REQUEST_ID_CTX.reset(token)

    captured = capfd.readouterr()
    lines = [line for line in captured.err.splitlines() if line]
    assert lines, "expected at least one log line"

    payload = json.loads(lines[-1])
    assert payload["message"] == "hello"
    assert payload["foo"] == "bar"
    assert payload["request_id"] == "req-123"
