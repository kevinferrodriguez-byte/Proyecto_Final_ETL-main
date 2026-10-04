import logging

import pytest

import src.extract.http_client as http_client_module
from src.extract.http_client import HttpClient
from fakes.fake_response import FakeResponse
from fakes.fake_session import FakeSession

URL = "https://ine.test/ES/DATOS_TABLA/56934"
REQUEST_CONFIG = {"timeout_seconds": 1, "max_retries": 3, "retry_backoff_seconds": 2, "retry_on_status": [429, 500, 502, 503, 504]}


def build_client(monkeypatch, events):
    FakeSession({URL: events}).install(monkeypatch)
    monkeypatch.setattr(http_client_module.time, "sleep", lambda seconds: None)
    return HttpClient(REQUEST_CONFIG)


def test_retry_is_logged_as_warning(monkeypatch, caplog):
    client = build_client(monkeypatch, [FakeResponse(503, b"", URL), FakeResponse(200, b"[]", URL)])
    caplog.set_level(logging.INFO, logger="src")

    client.get(URL)

    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert warnings == [f"HTTP 503 en {URL} (intento 1/4); nuevo intento en 2.0 s."]


def test_non_retryable_error_is_logged_before_failing(monkeypatch, caplog):
    client = build_client(monkeypatch, [FakeResponse(404, b"", URL)])
    caplog.set_level(logging.INFO, logger="src")

    with pytest.raises(ValueError, match="HTTP 404"):
        client.get(URL)

    errors = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].startswith(f"HTTP 404 en {URL}")


def test_closed_client_reports_its_state_and_refuses_new_requests():
    from src.extract.http_client import HttpClient

    client = HttpClient({"timeout_seconds": 1, "max_retries": 0, "retry_backoff_seconds": 0, "retry_on_status": []})
    assert client.closed is False

    client.close()
    client.close()  # idempotente

    assert client.closed is True
    with pytest.raises(RuntimeError, match="ya está cerrada"):
        client.get("https://example.test")
