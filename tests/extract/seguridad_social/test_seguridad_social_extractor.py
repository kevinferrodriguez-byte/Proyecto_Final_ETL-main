from pathlib import Path
import hashlib
import json

import pytest

import src.extract.http_client as http_client_module
from src.extract.bronze_integrity import BronzeIntegrityChecker
from src.extract.seguridad_social.seguridad_social_extractor import SeguridadSocialExtractor
from fakes.fake_response import FakeResponse
from fakes.fake_seguridad_social import FILE_IDS, default_contents, seguridad_social_config
from fakes.fake_session import FakeSession

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def source(tmp_path):
    return seguridad_social_config(tmp_path)["sources"]["seguridad_social"]


def ok(config, file_id, content):
    url = config["files"][file_id]["url"]
    return FakeResponse(200, content, url, {"Content-Type": XLSX_TYPE})


def build(tmp_path, monkeypatch, events_by_file):
    config = source(tmp_path)
    session = FakeSession({config["files"][file_id]["url"]: events for file_id, events in events_by_file.items()})
    session.install(monkeypatch)
    delays = []
    monkeypatch.setattr(http_client_module.time, "sleep", delays.append)
    return {"config": config, "session": session, "delays": delays, "extractor": SeguridadSocialExtractor(config)}


def successful(tmp_path, runs=1):
    config = source(tmp_path)
    contents = default_contents()
    return {file_id: [ok(config, file_id, contents[file_id]) for _ in range(runs)] for file_id in FILE_IDS}


def stored_payloads(config):
    return sorted(Path(config["storage"]["payloads_path"]).glob("*.xlsx"))


def manifests(config):
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path(config["storage"]["manifests_path"]).glob("*.manifest.json"))]


def test_extraction_saves_original_bytes_with_xlsx_extension_and_sha256(tmp_path, monkeypatch):
    context = build(tmp_path, monkeypatch, successful(tmp_path))
    contents = default_contents()

    result = context["extractor"].extract_files(FILE_IDS)

    assert [record["file_id"] for record in result["records"]] == list(FILE_IDS)
    for record in result["records"]:
        path = Path(record["path"])
        assert path.read_bytes() == contents[record["file_id"]]
        assert record["sha256"] == hashlib.sha256(contents[record["file_id"]]).hexdigest()
        assert record["size_bytes"] == len(contents[record["file_id"]])
        assert record["status_code"] == 200
        assert record["url"] == context["config"]["files"][record["file_id"]]["url"]
        assert record["content_type"] == XLSX_TYPE
        assert path.name.startswith(f"{record['file_id']}_") and path.name.endswith(".xlsx")
        assert ".xls.xls" not in path.name
    assert [call["timeout"] for call in context["session"].calls] == [60, 60]
    assert context["session"].closed is False
    context["extractor"].close()
    assert context["session"].closed is True


def test_manifest_records_traceability_and_passes_integrity_check(tmp_path, monkeypatch):
    context = build(tmp_path, monkeypatch, successful(tmp_path))

    result = context["extractor"].extract_files(FILE_IDS)

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["run_id"] == result["run_id"] and result["run_id"].startswith("seguridad_social_")
    assert manifest["status"] == "completada" and manifest["error"] is None
    assert manifest["source"] == "Seguridad Social"
    assert manifest["files_requested"] == list(FILE_IDS)
    for entry in manifest["payloads"]:
        assert not Path(entry["path"]).is_absolute()
        assert entry["validations"]["xlsx_valid"] and entry["validations"]["sheet_present"]
        assert entry["downloaded_at_utc"].endswith("Z")
        assert entry["url"].startswith("https://seg-social.test/")
    storage = context["config"]["storage"]
    report = BronzeIntegrityChecker(storage["payloads_path"], storage["manifests_path"], [storage["unmanifested_path"]]).check()
    assert report["ok"] and report["payloads_checked"] == 2 and report["manifests_checked"] == 1


def test_second_run_keeps_previous_bronze_files_untouched(tmp_path, monkeypatch):
    context = build(tmp_path, monkeypatch, successful(tmp_path, runs=2))
    first = context["extractor"].extract_files(FILE_IDS)
    snapshot = {path: path.read_bytes() for path in stored_payloads(context["config"])}

    second = context["extractor"].extract_files(FILE_IDS)

    assert first["run_id"] != second["run_id"]
    assert len(stored_payloads(context["config"])) == 4
    assert all(path.read_bytes() == content for path, content in snapshot.items())
    assert len(manifests(context["config"])) == 2


def test_retryable_status_is_retried_before_saving(tmp_path, monkeypatch):
    events = successful(tmp_path)
    config = source(tmp_path)
    events["afiliados_alta"].insert(0, FakeResponse(503, b"", config["files"]["afiliados_alta"]["url"]))
    context = build(tmp_path, monkeypatch, events)

    result = context["extractor"].extract_files(FILE_IDS)

    assert len(result["records"]) == 2
    assert context["delays"] == [2]
    assert len(context["session"].calls_to(config["files"]["afiliados_alta"]["url"])) == 2


def test_http_error_stores_nothing_for_that_file_and_writes_failed_manifest(tmp_path, monkeypatch):
    events = successful(tmp_path)
    config = source(tmp_path)
    events["pensionistas_nomina"] = [FakeResponse(404, b"Not Found", config["files"]["pensionistas_nomina"]["url"])]
    context = build(tmp_path, monkeypatch, events)

    with pytest.raises(ValueError, match="HTTP 404"):
        context["extractor"].extract_files(FILE_IDS)

    assert [path.name.split("_2")[0] for path in stored_payloads(context["config"])] == ["afiliados_alta"]
    [manifest] = manifests(context["config"])
    assert manifest["status"] == "fallida" and "HTTP 404" in manifest["error"]
    assert [entry["file_id"] for entry in manifest["payloads"]] == ["afiliados_alta"]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "llegó vacío"),
        (b"<html><body>Not found</body></html>", "página HTML"),
        (b"PK\x03\x04no es un zip", "no se puede abrir"),
    ],
)
def test_invalid_content_is_rejected_without_saving(tmp_path, monkeypatch, content, message):
    config = source(tmp_path)
    context = build(tmp_path, monkeypatch, {"afiliados_alta": [ok(config, "afiliados_alta", content)]})

    with pytest.raises(ValueError, match=message):
        context["extractor"].extract_file("afiliados_alta")

    assert stored_payloads(context["config"]) == []


def test_workbook_without_configured_sheet_is_rejected(tmp_path, monkeypatch):
    config = source(tmp_path)
    content = default_contents()["afiliados_alta"]
    context = build(tmp_path, monkeypatch, {"pensionistas_nomina": [ok(config, "pensionistas_nomina", content)]})

    with pytest.raises(ValueError, match=r"no contiene las hojas \['Nº Pens. Clases'"):
        context["extractor"].extract_file("pensionistas_nomina")

    assert stored_payloads(context["config"]) == []


def test_unknown_file_is_rejected_before_any_request(tmp_path, monkeypatch):
    context = build(tmp_path, monkeypatch, {})

    with pytest.raises(ValueError, match="no está configurado"):
        context["extractor"].extract_file("desconocido")

    assert context["session"].calls == []
