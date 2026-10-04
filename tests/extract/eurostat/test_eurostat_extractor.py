from pathlib import Path
import hashlib
import json

import pytest

import src.extract.http_client as http_client_module
from src.extract.bronze_integrity import BronzeIntegrityChecker
from src.extract.eurostat.eurostat_extractor import EurostatExtractor
from fakes.fake_eurostat import DATASET_IDS, default_payloads, eurostat_config
from fakes.fake_response import FakeResponse
from fakes.fake_session import FakeSession


def source(tmp_path):
    return eurostat_config(tmp_path)["sources"]["eurostat"]


def url(config, dataset_id):
    return f"{config['base_url']}/{config['datasets'][dataset_id]['code']}"


def build(tmp_path, monkeypatch, contents):
    config = source(tmp_path)
    routes = {url(config, dataset_id): [FakeResponse(200, content, url(config, dataset_id))] for dataset_id, content in contents.items()}
    session = FakeSession(routes)
    session.install(monkeypatch)
    monkeypatch.setattr(http_client_module.time, "sleep", lambda seconds: None)
    return config, session, EurostatExtractor(config)


def encoded():
    return {dataset_id: json.dumps(payload).encode("utf-8") for dataset_id, payload in default_payloads().items()}


def test_original_bytes_are_stored_with_source_version_and_a_complete_manifest(tmp_path, monkeypatch):
    contents = encoded()
    config, session, extractor = build(tmp_path, monkeypatch, contents)

    result = extractor.extract_datasets(DATASET_IDS)

    for record in result["records"]:
        assert Path(record["path"]).read_bytes() == contents[record["dataset_id"]]
        assert record["sha256"] == hashlib.sha256(contents[record["dataset_id"]]).hexdigest()
        assert record["source_updated"] == "2026-09-29T11:00:00+0200"
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completada"
    assert [entry["dataset_id"] for entry in manifest["payloads"]] == list(DATASET_IDS)
    assert session.calls_to(url(config, "gasto_pensiones"))[0]["params"]["unit"] == ["MIO_EUR", "PC_GDP"]
    storage = config["storage"]
    report = BronzeIntegrityChecker(storage["payloads_path"], storage["manifests_path"], [storage["unmanifested_path"]]).check()
    assert report["ok"]


def test_api_error_payload_is_not_stored_and_the_manifest_records_the_failure(tmp_path, monkeypatch):
    error = json.dumps({"error": [{"status": 400, "label": "bad filter"}]}).encode("utf-8")
    config, _, extractor = build(tmp_path, monkeypatch, {"pib": error})

    with pytest.raises(ValueError, match="error de la API"):
        extractor.extract_datasets(["pib"])

    assert not list(Path(config["storage"]["payloads_path"]).glob("*.json"))
    manifest_path = next(Path(config["storage"]["manifests_path"]).glob("*.manifest.json"))
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "fallida"


def test_empty_selection_is_rejected(tmp_path, monkeypatch):
    payload = default_payloads()["pib"]
    payload["value"] = {}
    _, _, extractor = build(tmp_path, monkeypatch, {"pib": json.dumps(payload).encode("utf-8")})

    with pytest.raises(ValueError, match="no contiene observaciones"):
        extractor.extract_datasets(["pib"])


def test_context_manager_closes_the_connection_even_when_extraction_fails(tmp_path, monkeypatch):
    error = json.dumps({"error": [{"status": 400, "label": "bad filter"}]}).encode("utf-8")
    config, _, _ = build(tmp_path, monkeypatch, {"pib": error})

    with pytest.raises(ValueError):
        with EurostatExtractor(config) as extractor:
            assert extractor.closed is False
            extractor.extract_datasets(["pib"])

    assert extractor.closed is True
