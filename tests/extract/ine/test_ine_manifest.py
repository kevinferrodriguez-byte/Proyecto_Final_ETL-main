from pathlib import Path
import hashlib
import json

import pytest

import src.extract.http_client as http_client_module
from src.extract.ine.ine_extractor import IneExtractor
from fakes.fake_session import FakeSession
from fakes.ine_catalog import PAYLOADS, IneCatalog

PAYLOAD_FIELDS = {
    "source",
    "table_id",
    "query",
    "url",
    "parameters",
    "downloaded_at_utc",
    "status_code",
    "size_bytes",
    "sha256",
    "path",
    "validations",
    "known_behaviors",
}


def run_extraction(tmp_path, monkeypatch, table_ids, known_behaviors):
    catalog = IneCatalog(tmp_path)
    catalog.config["tables"]["56934"]["known_behaviors"] = known_behaviors
    FakeSession(catalog.routes(catalog.successful_events())).install(monkeypatch)
    monkeypatch.setattr(http_client_module.time, "sleep", lambda seconds: None)
    return {"catalog": catalog, "extractor": IneExtractor(catalog.config), "table_ids": table_ids}


def read_manifest(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_extract_tables_writes_one_manifest_with_all_fields(tmp_path, monkeypatch):
    context = run_extraction(tmp_path, monkeypatch, ["56934"], ["El orden de las entradas varía."])

    result = context["extractor"].extract_tables(context["table_ids"])
    manifest = read_manifest(result["manifest_path"])

    assert Path(result["manifest_path"]).parent == context["catalog"].manifests_path
    assert Path(result["manifest_path"]).name == f"{result['run_id']}.manifest.json"
    assert manifest["run_id"] == result["run_id"]
    assert manifest["status"] == "completada"
    assert manifest["error"] is None
    assert manifest["tables_requested"] == ["56934"]
    assert manifest["started_at_utc"].endswith("Z") and manifest["finished_at_utc"].endswith("Z")
    assert [payload["query"] for payload in manifest["payloads"]] == list(PAYLOADS)
    for payload in manifest["payloads"]:
        assert set(payload) == PAYLOAD_FIELDS
        assert payload["status_code"] == 200
        assert payload["parameters"]["tv"]
        assert payload["known_behaviors"] == ["El orden de las entradas varía."]
        assert payload["validations"]["json_valid"] and payload["validations"]["series_present"]
        assert payload["validations"]["data_present"]
    assert [payload["validations"]["series_count"] for payload in manifest["payloads"]] == [1, 1, 2]
    assert [payload["validations"]["observation_count"] for payload in manifest["payloads"]] == [1, 1, 1]


def test_manifest_matches_each_payload_by_relative_path_and_sha256(tmp_path, monkeypatch):
    context = run_extraction(tmp_path, monkeypatch, ["56934"], [])

    result = context["extractor"].extract_tables(context["table_ids"])
    manifest_directory = Path(result["manifest_path"]).parent
    payloads = read_manifest(result["manifest_path"])["payloads"]

    stored = {path.resolve() for path in context["catalog"].payloads_path.glob("*.json")}
    listed = {(manifest_directory / payload["path"]).resolve() for payload in payloads}
    assert listed == stored
    for payload in payloads:
        content = (manifest_directory / payload["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == payload["sha256"]
        assert len(content) == payload["size_bytes"]


def test_failed_run_still_writes_manifest_for_saved_payloads(tmp_path, monkeypatch):
    context = run_extraction(tmp_path, monkeypatch, ["56934", "99999"], [])

    with pytest.raises(ValueError, match="99999"):
        context["extractor"].extract_tables(context["table_ids"])

    manifests = list(context["catalog"].manifests_path.glob("*.manifest.json"))
    manifest = read_manifest(manifests[0])
    assert len(manifests) == 1
    assert manifest["status"] == "fallida"
    assert "99999" in manifest["error"]
    assert len(manifest["payloads"]) == 3


def test_manifest_write_failure_reports_payloads_left_without_manifest(tmp_path, monkeypatch):
    context = run_extraction(tmp_path, monkeypatch, ["56934"], [])
    context["catalog"].payloads_path.mkdir(parents=True)
    context["catalog"].manifests_path.write_text("no es una carpeta", encoding="utf-8")

    with pytest.raises(OSError, match="Payloads sin manifiesto: 56934_detalle_.*56934_total_edad_.*56934_semiintervalos_edad_"):
        context["extractor"].extract_tables(context["table_ids"])
