from pathlib import Path
import json

import pytest

from src.utils.run_manifest import RunManifest
from fakes.failing_file import FailingFile

MANIFEST = {
    "run_id": "ine_20260926T120000.123456Z",
    "payloads": [{"path": "../56934_detalle_20260926T120000.200000Z.json"}, {"path": "../6566_detalle_20260926T120001.300000Z.json"}],
}


def test_write_creates_manifest_named_by_run_id(tmp_path):
    path = Path(RunManifest(tmp_path / "manifests").write(MANIFEST))

    assert path == tmp_path / "manifests" / "ine_20260926T120000.123456Z.manifest.json"
    assert json.loads(path.read_text(encoding="utf-8")) == MANIFEST


def test_write_refuses_to_overwrite_and_lists_payloads_without_manifest(tmp_path):
    manifest = RunManifest(tmp_path)
    path = Path(manifest.write(MANIFEST))
    original = path.read_bytes()

    with pytest.raises(FileExistsError, match="Payloads sin manifiesto: 56934_detalle_20260926T120000.200000Z.json, 6566_detalle"):
        manifest.write(MANIFEST)

    assert path.read_bytes() == original


def test_write_failure_removes_partial_file_and_lists_payloads_without_manifest(tmp_path, monkeypatch):
    original_open = Path.open

    def failing_open(path, mode="r"):
        return FailingFile(original_open(path, mode))

    monkeypatch.setattr(Path, "open", failing_open)

    with pytest.raises(OSError, match="No queda espacio.*Payloads sin manifiesto: 56934_detalle"):
        RunManifest(tmp_path).write(MANIFEST)

    assert list(tmp_path.iterdir()) == []


def test_unusable_manifest_directory_lists_payloads_without_manifest(tmp_path):
    blocked_directory = tmp_path / "manifests"
    blocked_directory.write_text("no es una carpeta", encoding="utf-8")

    with pytest.raises(OSError, match="carpeta de manifiestos.*Payloads sin manifiesto: 56934_detalle"):
        RunManifest(blocked_directory).write(MANIFEST)


def test_relative_path_points_from_manifest_directory_to_payload(tmp_path):
    manifest = RunManifest(tmp_path / "ine" / "manifests")

    assert manifest.relative_path(tmp_path / "ine" / "56934_detalle.json") == "../56934_detalle.json"
