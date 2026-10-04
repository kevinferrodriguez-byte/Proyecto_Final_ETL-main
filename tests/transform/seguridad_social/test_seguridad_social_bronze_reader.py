import json
from pathlib import Path

import pytest

from src.transform.seguridad_social.seguridad_social_bronze_reader import SeguridadSocialBronzeReader
from fakes.fake_seguridad_social import FILE_IDS, FakeSeguridadSocialBronze, seguridad_social_config


def context(tmp_path):
    config = seguridad_social_config(tmp_path)
    storage = config["sources"]["seguridad_social"]["storage"]
    return FakeSeguridadSocialBronze(config), SeguridadSocialBronzeReader(storage)


def test_latest_completed_run_is_used_and_failed_runs_are_ignored(tmp_path):
    bronze, reader = context(tmp_path)
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z")
    bronze.run("seguridad_social_2", "2026-09-27T01:00:00.000000Z")
    bronze.run("seguridad_social_3", "2026-09-28T01:00:00.000000Z", status="fallida")

    payloads = reader.latest_payloads(FILE_IDS)

    assert {payload["run_id"] for payload in payloads.values()} == {"seguridad_social_2"}
    assert payloads["afiliados_alta"]["path"].name == "afiliados_alta_seguridad_social_2.xlsx"


def test_missing_file_is_an_error(tmp_path):
    bronze, reader = context(tmp_path)
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z", contents={"afiliados_alta": b"x"})

    with pytest.raises(ValueError, match="pensionistas_nomina"):
        reader.latest_payloads(FILE_IDS)


def test_unmanifested_folder_is_never_read(tmp_path):
    bronze, reader = context(tmp_path)
    entries = bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z")
    manifest_path = next(Path(bronze.storage["manifests_path"]).glob("*.manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["payloads"][0]["path"] = "../_sin_manifiesto/" + Path(entries[0]["path"]).name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="_sin_manifiesto"):
        reader.latest_payloads(FILE_IDS)


def test_read_sheet_returns_raw_cells_and_rejects_missing_sheet(tmp_path):
    bronze, reader = context(tmp_path)
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z")
    payloads = reader.latest_payloads(FILE_IDS)

    grid = reader.read_sheet(payloads["afiliados_alta"], "Hoja1")

    assert grid.iat[2, 0] == "Periodo"
    with pytest.raises(ValueError, match="no contiene la hoja 'Nº Pens. Clases'"):
        reader.read_sheet(payloads["afiliados_alta"], "Nº Pens. Clases")


def test_corrupt_workbook_is_reported_as_value_error(tmp_path):
    bronze, reader = context(tmp_path)
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z", contents={"afiliados_alta": b"PK\x03\x04roto", "pensionistas_nomina": b"x"})
    payloads = reader.latest_payloads(FILE_IDS)

    with pytest.raises(ValueError, match="no se puede leer como libro Excel"):
        reader.read_sheet(payloads["afiliados_alta"], "Hoja1")
