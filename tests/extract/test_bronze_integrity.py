import hashlib
import json

from src.extract.bronze_integrity import BronzeIntegrityChecker
from src.utils.run_manifest import RunManifest


def write_payload(bronze, name, content):
    path = bronze / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def write_manifest(bronze, run_id, payload_paths):
    manifest = RunManifest(bronze / "manifests")
    entries = [
        {
            "path": manifest.relative_path(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in payload_paths
    ]
    manifest.write({"run_id": run_id, "payloads": entries})


def check(bronze):
    return BronzeIntegrityChecker(bronze, bronze / "manifests", [bronze / "_sin_manifiesto"]).check()


def snapshot(bronze):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in bronze.rglob("*") if path.is_file()}


def clean_bronze(tmp_path):
    bronze = tmp_path / "ine"
    first = write_payload(bronze, "56934_detalle_1.json", b'[{"Data": [1]}]')
    second = write_payload(bronze, "6566_detalle_1.json", b'[{"Data": [2]}]')
    write_manifest(bronze, "run_1", [first, second])
    write_payload(bronze, "_sin_manifiesto/56934_detalle_0.json", b"[]")
    write_payload(bronze, "_sin_manifiesto/LEEME.md", b"Descargas sin manifiesto")
    return {"bronze": bronze, "first": first, "second": second}


def test_clean_folder_passes_and_ignores_unmanifested_directory(tmp_path):
    bronze = clean_bronze(tmp_path)["bronze"]

    report = check(bronze)

    assert report["ok"]
    assert report["payloads_checked"] == 2
    assert report["manifests_checked"] == 1
    assert [report[key] for key in ("orphans", "missing", "mismatches", "duplicates", "invalid_manifests")] == [[], [], [], [], []]


def test_orphan_payload_is_reported(tmp_path):
    bronze = clean_bronze(tmp_path)["bronze"]
    write_payload(bronze, "24309_detalle_1.json", b'[{"Data": [3]}]')

    report = check(bronze)

    assert not report["ok"]
    assert report["orphans"] == ["24309_detalle_1.json"]


def test_missing_payload_is_reported(tmp_path):
    context = clean_bronze(tmp_path)
    context["second"].unlink()

    report = check(context["bronze"])

    assert not report["ok"]
    assert report["missing"] == [{"payload": "6566_detalle_1.json", "manifest": "run_1.manifest.json"}]
    assert report["orphans"] == []


def test_altered_hash_with_same_size_is_reported(tmp_path):
    context = clean_bronze(tmp_path)
    original = context["first"].read_bytes()
    context["first"].write_bytes(original.replace(b"1", b"9"))

    report = check(context["bronze"])

    assert not report["ok"]
    assert len(report["mismatches"]) == 1
    mismatch = report["mismatches"][0]
    assert mismatch["payload"] == "56934_detalle_1.json"
    assert mismatch["expected_size_bytes"] == mismatch["actual_size_bytes"] == len(original)
    assert mismatch["expected_sha256"] == hashlib.sha256(original).hexdigest()
    assert mismatch["actual_sha256"] == hashlib.sha256(context["first"].read_bytes()).hexdigest()


def test_altered_size_is_reported(tmp_path):
    context = clean_bronze(tmp_path)
    context["second"].write_bytes(b'[{"Data": [2, 3]}]')

    report = check(context["bronze"])

    assert [mismatch["payload"] for mismatch in report["mismatches"]] == ["6566_detalle_1.json"]
    assert report["mismatches"][0]["actual_size_bytes"] != report["mismatches"][0]["expected_size_bytes"]


def test_payload_referenced_by_two_manifests_is_reported(tmp_path):
    context = clean_bronze(tmp_path)
    write_manifest(context["bronze"], "run_2", [context["first"]])

    report = check(context["bronze"])

    assert not report["ok"]
    assert report["duplicates"] == [
        {"payload": "56934_detalle_1.json", "manifests": ["run_1.manifest.json", "run_2.manifest.json"]}
    ]


def test_payload_listed_twice_in_one_manifest_is_reported(tmp_path):
    bronze = tmp_path / "ine"
    payload = write_payload(bronze, "56934_detalle_1.json", b'[{"Data": [1]}]')
    write_manifest(bronze, "run_1", [payload, payload])

    report = check(bronze)

    assert report["duplicates"] == [
        {"payload": "56934_detalle_1.json", "manifests": ["run_1.manifest.json", "run_1.manifest.json"]}
    ]


def test_unreadable_manifest_is_reported(tmp_path):
    bronze = clean_bronze(tmp_path)["bronze"]
    (bronze / "manifests" / "run_roto.manifest.json").write_text("{", encoding="utf-8")

    report = check(bronze)

    assert not report["ok"]
    assert report["invalid_manifests"] == ["run_roto.manifest.json"]


def test_check_never_modifies_files(tmp_path):
    context = clean_bronze(tmp_path)
    write_payload(context["bronze"], "24309_detalle_1.json", b"[]")
    context["first"].write_bytes(b"alterado")
    write_manifest(context["bronze"], "run_2", [context["second"]])
    before = snapshot(context["bronze"])

    report = check(context["bronze"])

    assert not report["ok"]
    assert snapshot(context["bronze"]) == before


def test_empty_source_without_directories_passes(tmp_path):
    report = check(tmp_path / "sin_datos")

    assert report["ok"]
    assert report["payloads_checked"] == 0
    assert report["manifests_checked"] == 0


def test_manifest_payload_entries_keep_their_manifest_format(tmp_path):
    bronze = clean_bronze(tmp_path)["bronze"]
    manifest = json.loads((bronze / "manifests" / "run_1.manifest.json").read_text(encoding="utf-8"))

    assert [entry["path"] for entry in manifest["payloads"]] == ["../56934_detalle_1.json", "../6566_detalle_1.json"]
