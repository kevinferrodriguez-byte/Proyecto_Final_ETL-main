from datetime import datetime, timezone
from pathlib import Path
import hashlib

import pytest

import src.extract.bronze_storage as bronze_storage_module
from src.extract.bronze_storage import BronzeStorage
from fakes.fake_clock import FakeClock


def test_save_names_file_with_prefix_and_microsecond_timestamp(tmp_path, monkeypatch):
    moment = datetime(2026, 9, 25, 12, 0, 0, 123456, tzinfo=timezone.utc)
    monkeypatch.setattr(bronze_storage_module, "datetime", FakeClock(moment))
    payload = b'[{"Data": [1]}]'

    stored = BronzeStorage(tmp_path).save(payload, "56934_detalle", "json")

    assert Path(stored["path"]).name == "56934_detalle_20260925T120000.123456Z.json"
    assert stored["downloaded_at_utc"] == "2026-09-25T12:00:00.123456Z"
    assert stored["sha256"] == hashlib.sha256(payload).hexdigest()
    assert stored["size_bytes"] == len(payload)


def test_save_refuses_to_overwrite_existing_file(tmp_path, monkeypatch):
    moment = datetime(2026, 9, 25, 12, 0, 0, 123456, tzinfo=timezone.utc)
    monkeypatch.setattr(bronze_storage_module, "datetime", FakeClock(moment))
    storage = BronzeStorage(tmp_path)
    stored = storage.save(b"original", "56934_detalle", "json")

    with pytest.raises(FileExistsError, match="no se sobrescribe"):
        storage.save(b"nuevo", "56934_detalle", "json")

    assert Path(stored["path"]).read_bytes() == b"original"
    assert len(list(tmp_path.iterdir())) == 1
