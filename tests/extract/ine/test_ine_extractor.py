from pathlib import Path
import hashlib

import pytest
import requests

import src.extract.http_client as http_client_module
from src.extract.ine.ine_extractor import IneExtractor
from fakes.fake_response import FakeResponse
from fakes.fake_session import FakeSession
from fakes.ine_catalog import PAYLOADS, IneCatalog


def build(tmp_path, monkeypatch, data_events):
    catalog = IneCatalog(tmp_path)
    session = FakeSession(catalog.routes(data_events))
    session.install(monkeypatch)
    delays = []
    monkeypatch.setattr(http_client_module.time, "sleep", delays.append)
    return {"catalog": catalog, "session": session, "delays": delays, "extractor": IneExtractor(catalog.config)}


def stored_files(tmp_path):
    return sorted(path for path in tmp_path.rglob("*") if path.is_file())


def test_extract_table_saves_detail_and_control_bytes_unchanged(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    context = build(tmp_path, monkeypatch, catalog.successful_events())

    records = context["extractor"].extract_table("56934")

    assert [record["query"] for record in records] == list(PAYLOADS)
    for record, payload in zip(records, PAYLOADS.values()):
        path = Path(record["path"])
        assert path.read_bytes() == payload
        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
        assert record["size_bytes"] == len(payload)
        assert record["status_code"] == 200
        assert record["url"] == f"{catalog.data_url}?consulta={record['query']}"
        assert record["downloaded_at_utc"].endswith("Z")
        assert path.parent == catalog.payloads_path
        assert path.name.startswith(f"56934_{record['query']}_")
    assert len(stored_files(tmp_path)) == 3
    assert context["session"].opened == 1


def test_extract_table_requests_complete_ages_in_detail_and_total_in_control(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    context = build(tmp_path, monkeypatch, catalog.successful_events())

    records = context["extractor"].extract_table("56934")
    data_calls = context["session"].calls_to(catalog.data_url)
    detail_tv = records[0]["parameters"]["tv"]

    assert len(detail_tv) == 109
    assert sum(1 for value in detail_tv if value.startswith("355:")) == 105
    assert [value for value in detail_tv if value.startswith("357:")] == ["357:311059"]
    assert [value for value in detail_tv if value.startswith("18:")] == ["18:451", "18:452", "18:453"]
    assert records[1]["parameters"]["tv"] == ["18:451", "18:452", "18:453", "356:15668"]
    assert records[2]["parameters"]["tv"] == ["18:451", "18:452", "18:453", "357:15100", "357:15071"]
    assert data_calls[0]["params"] == [("tv", value) for value in detail_tv] + [("tip", "M")]
    assert data_calls[1]["params"] == [("tv", value) for value in records[1]["parameters"]["tv"]] + [("tip", "M")]
    assert [record["parameters"]["tip"] for record in records] == ["M", "M", "M"]


def test_invalid_json_raises_and_saves_nothing(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    context = build(tmp_path, monkeypatch, [catalog.data_response(b"<html>error</html>", "detalle")])

    with pytest.raises(ValueError, match="no es JSON válido"):
        context["extractor"].extract_table("56934")

    assert stored_files(tmp_path) == []


def test_invalid_control_payload_prevents_saving_detail(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    events = [catalog.data_response(PAYLOADS["detalle"], "detalle"), catalog.data_response(b"{", "total_edad")]
    context = build(tmp_path, monkeypatch, events)

    with pytest.raises(ValueError, match="no es JSON válido"):
        context["extractor"].extract_table("56934")

    assert stored_files(tmp_path) == []


def test_empty_body_raises_and_saves_nothing(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    context = build(tmp_path, monkeypatch, [catalog.data_response(b" \r\n", "detalle")])

    with pytest.raises(ValueError, match="llegó vacía"):
        context["extractor"].extract_table("56934")

    assert stored_files(tmp_path) == []


def test_response_without_series_raises_and_saves_nothing(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    context = build(tmp_path, monkeypatch, [catalog.data_response(b"[]", "detalle")])

    with pytest.raises(ValueError, match="no devolvió series"):
        context["extractor"].extract_table("56934")

    assert stored_files(tmp_path) == []


def test_series_without_data_raise_and_save_nothing(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    context = build(tmp_path, monkeypatch, [catalog.data_response(b'[{"COD": "ECP1", "Data": []}]', "detalle")])

    with pytest.raises(ValueError, match="series sin datos"):
        context["extractor"].extract_table("56934")

    assert stored_files(tmp_path) == []


def test_429_waits_for_retry_after_before_retrying(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    events = [FakeResponse(429, b"", catalog.data_url, {"Retry-After": "7"})] + catalog.successful_events()
    context = build(tmp_path, monkeypatch, events)

    records = context["extractor"].extract_table("56934")

    assert context["delays"] == [7.0]
    assert len(context["session"].calls_to(catalog.data_url)) == 4
    assert Path(records[0]["path"]).read_bytes() == PAYLOADS["detalle"]


def test_404_fails_without_retrying(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    context = build(tmp_path, monkeypatch, [FakeResponse(404, b"", catalog.data_url)])

    with pytest.raises(ValueError, match="HTTP 404.*config/config.yaml"):
        context["extractor"].extract_table("56934")

    assert len(context["session"].calls_to(catalog.data_url)) == 1
    assert context["delays"] == []
    assert stored_files(tmp_path) == []


def test_503_is_retried_until_success(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    events = [FakeResponse(503, b"", catalog.data_url)] + catalog.successful_events()
    context = build(tmp_path, monkeypatch, events)

    records = context["extractor"].extract_table("56934")

    assert context["delays"] == [catalog.config["request"]["retry_backoff_seconds"]]
    assert len(context["session"].calls_to(catalog.data_url)) == 4
    assert [Path(record["path"]).read_bytes() for record in records] == list(PAYLOADS.values())


def test_timeouts_exhaust_retries_and_save_nothing(tmp_path, monkeypatch):
    catalog = IneCatalog(tmp_path)
    attempts = catalog.config["request"]["max_retries"] + 1
    events = [requests.Timeout("sin respuesta") for attempt in range(attempts)]
    context = build(tmp_path, monkeypatch, events)

    with pytest.raises(TimeoutError, match=f"agotó {attempts} intentos"):
        context["extractor"].extract_table("56934")

    assert len(context["session"].calls_to(catalog.data_url)) == attempts
    assert len(context["delays"]) == attempts - 1
    assert stored_files(tmp_path) == []


def test_close_releases_shared_session(tmp_path, monkeypatch):
    context = build(tmp_path, monkeypatch, [])

    context["extractor"].close()

    assert context["session"].closed
