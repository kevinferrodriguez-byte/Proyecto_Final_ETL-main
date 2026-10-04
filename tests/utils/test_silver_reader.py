import pytest

from src.utils.silver_reader import SilverReader
from fakes.fake_silver import DATASET, FakeSilver
from fakes.silver_samples import population


def test_reader_returns_latest_completed_silver_run_with_verified_hash(tmp_path):
    silver = FakeSilver(tmp_path / "silver")
    silver.publish("silver_1", "2026-09-26T01:00:00.000000Z", population(2024))
    silver.publish("silver_2", "2026-09-26T02:00:00.000000Z", population(2025))

    result = SilverReader(tmp_path / "silver" / "manifests", DATASET).latest()

    assert result["run_id"] == "silver_2"
    assert set(result["frame"]["anyo"]) == {2025}


def test_reader_ignores_failed_manifests(tmp_path):
    silver = FakeSilver(tmp_path / "silver")
    silver.publish("silver_1", "2026-09-26T01:00:00.000000Z", population(2025))
    silver.manifest.write({"run_id": "silver_2", "status": "fallida", "started_at_utc": "2026-09-26T02:00:00.000000Z", "payloads": []})

    assert SilverReader(tmp_path / "silver" / "manifests", DATASET).latest()["run_id"] == "silver_1"


def test_reader_rejects_output_that_no_longer_matches_its_manifest(tmp_path):
    silver = FakeSilver(tmp_path / "silver")
    path = silver.publish("silver_1", "2026-09-26T01:00:00.000000Z", population(2025))
    path.write_bytes(path.read_bytes() + b"x")

    with pytest.raises(ValueError, match="no coincide con el manifiesto de Plata"):
        SilverReader(tmp_path / "silver" / "manifests", DATASET).latest()


def test_reader_requires_a_completed_silver_manifest(tmp_path):
    with pytest.raises(ValueError, match="No hay manifiestos de Plata completados"):
        SilverReader(tmp_path / "silver" / "manifests", DATASET).latest()
