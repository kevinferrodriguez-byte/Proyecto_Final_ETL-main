import pytest

from src.transform.ine.ine_bronze_reader import IneBronzeReader
from fakes.fake_bronze import FakeBronze
from fakes.ine_payloads import migration_69758, point


def test_reader_selects_latest_completed_run_per_table_and_query(tmp_path):
    bronze = FakeBronze(tmp_path / "ine")
    bronze.run("ine_1", "2026-09-26T01:00:00.000000Z", {("69758", "detalle"): migration_69758([point(2021, 1.0)])})
    bronze.run("ine_2", "2026-09-26T02:00:00.000000Z", {("69758", "detalle"): migration_69758([point(2021, 2.0)])})
    bronze.run("ine_3", "2026-09-26T03:00:00.000000Z", {("69758", "detalle"): migration_69758([point(2021, 3.0)])}, "fallida")
    reader = IneBronzeReader(bronze.storage_config())

    payloads = reader.latest_payloads(["69758"])

    assert [(payload["table_id"], payload["query"], payload["run_id"]) for payload in payloads] == [("69758", "detalle", "ine_2")]
    assert reader.read(payloads[0])[0]["Data"][0]["Valor"] == 2.0


def test_reader_requires_every_enabled_table(tmp_path):
    bronze = FakeBronze(tmp_path / "ine")
    bronze.run("ine_1", "2026-09-26T01:00:00.000000Z", {("69758", "detalle"): migration_69758([point(2021, 1.0)])})

    with pytest.raises(ValueError, match=r"No hay ejecuciones completadas de Bronce para las tablas INE \['6566'\]"):
        IneBronzeReader(bronze.storage_config()).latest_payloads(["69758", "6566"])


def test_reader_never_reads_unmanifested_directory(tmp_path):
    bronze = FakeBronze(tmp_path / "ine")
    entries = bronze.run("ine_1", "2026-09-26T01:00:00.000000Z", {("69758", "detalle"): migration_69758([point(2021, 1.0)])})
    moved = tmp_path / "ine" / "_sin_manifiesto"
    moved.mkdir()
    manifest_path = tmp_path / "ine" / "manifests" / "ine_1.manifest.json"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(entries[0]["path"], "../_sin_manifiesto/69758.json"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Plata no puede leer payloads de"):
        IneBronzeReader(bronze.storage_config()).latest_payloads(["69758"])
