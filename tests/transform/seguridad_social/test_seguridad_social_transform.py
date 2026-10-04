from pathlib import Path
import hashlib
import json

import pandas as pd
import pytest

from src.utils.silver_reader import SilverReader
from src.indicators.pensiones_indicadores import PensionesIndicadores
from src.transform.seguridad_social.seguridad_social_schema import AfiliadosSchema, PensionesSchema
from src.transform.seguridad_social.seguridad_social_transform import SeguridadSocialTransform
from src.indicators.kpi_ratio_schema import KpiRatioSchema
from fakes.fake_seguridad_social import FakeSeguridadSocialBronze, default_contents, seguridad_social_config
from fakes.seguridad_social_workbooks import afiliados_rows, months, workbook_bytes

GREEN = {"ok": True}


def context(tmp_path):
    config = seguridad_social_config(tmp_path)
    return config, FakeSeguridadSocialBronze(config), config["silver"]["seguridad_social"]


def reports(directory):
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path(directory).glob("*.quality.json"))]


def test_silver_writes_both_datasets_with_manifest_and_approved_report(tmp_path):
    config, bronze, silver = context(tmp_path)
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z")

    result = SeguridadSocialTransform(config).run(GREEN)

    afiliados = pd.read_parquet(result["paths"]["afiliados"])
    pensiones = pd.read_parquet(result["paths"]["pensiones"])
    AfiliadosSchema().validate(afiliados)
    PensionesSchema().validate(pensiones)
    assert Path(result["paths"]["afiliados"]).name == "stg_afiliados_mensual.parquet"
    assert Path(result["paths"]["pensiones"]).name == "stg_pensiones_cuantia.parquet"
    assert result["rows"] == {"stg_afiliados_mensual": 128, "stg_pensiones_cuantia": 31, "stg_pensiones_importe": 31}
    assert set(afiliados["run_id"]) == {"seguridad_social_1"} and set(afiliados["territorio"]) == {"ES"}
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["bronze_run_ids"] == ["seguridad_social_1"]
    assert [entry["file_id"] for entry in manifest["bronze_inputs"]] == ["afiliados_alta", "pensionistas_nomina"]
    for entry in manifest["payloads"]:
        path = (Path(result["manifest_path"]).parent / entry["path"]).resolve()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    [report] = reports(silver["manifests_path"])
    assert report["estado"] == "aprobado" and report["capa"] == "Plata Seguridad Social"
    assert report["metricas"]["pensiones_periodos_no_publicados"] == ["2026 Oct", "2026 Nov", "2026 Dic"]
    assert SilverReader(silver["manifests_path"], "stg_afiliados_mensual").latest()["run_id"] == result["run_id"]


def test_silver_refuses_bronze_without_green_integrity(tmp_path):
    config, bronze, silver = context(tmp_path)
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z")

    with pytest.raises(RuntimeError, match="integridad de Bronce"):
        SeguridadSocialTransform(config).run({"ok": False})

    assert reports(silver["manifests_path"])[0]["estado"] == "rechazado"
    assert not list(Path(silver["output_path"]).glob("*.parquet"))


def test_quality_failure_blocks_parquet_and_manifest(tmp_path):
    config, bronze, silver = context(tmp_path)
    rows = afiliados_rows(months("2016-01", "2026-08") + [(2020, 5)])
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z", {**default_contents(), "afiliados_alta": workbook_bytes({"Hoja1": rows})})

    with pytest.raises(ValueError, match="clave"):
        SeguridadSocialTransform(config).run(GREEN)

    [report] = reports(silver["manifests_path"])
    assert report["estado"] == "rechazado"
    assert [rule["regla"] for rule in report["reglas"] if rule["resultado"] == "falla"] == ["afiliados.clave_unica"]
    assert not list(Path(silver["output_path"]).glob("*.parquet"))
    assert not list(Path(silver["manifests_path"]).glob("*.manifest.json"))


def test_kpi_stage_reads_verified_silver_and_publishes_manifest(tmp_path):
    config, bronze, silver = context(tmp_path)
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z")
    silver_result = SeguridadSocialTransform(config).run(GREEN)

    kpi = PensionesIndicadores(config).run()

    frame = pd.read_parquet(kpi["path"])
    KpiRatioSchema().validate(frame)
    assert Path(kpi["path"]) == Path(config["indicadores"]["output_path"]) / "kpi_ratio_sostenibilidad_anual.parquet"
    assert frame["anyo"].tolist() == list(range(2016, 2026))
    assert kpi["silver_run_id"] == silver_result["run_id"] and kpi["bronze_run_ids"] == ["seguridad_social_1"]
    manifest = json.loads(Path(kpi["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["silver_run_id"] == silver_result["run_id"]
    assert "Capa de indicadores de Oro" in manifest["nota"]
    assert reports(config["indicadores"]["pensiones"]["manifests_path"])[0]["estado"] == "aprobado"
    assert SilverReader(silver["manifests_path"], "stg_pensiones_cuantia").latest()["run_id"] == silver_result["run_id"]


def test_kpi_stage_without_silver_fails_with_rejected_report(tmp_path):
    config, bronze, silver = context(tmp_path)

    with pytest.raises(ValueError, match="No hay manifiestos de Plata completados"):
        PensionesIndicadores(config).run()

    assert reports(config["indicadores"]["pensiones"]["manifests_path"])[0]["estado"] == "rechazado"


def test_kpi_stage_detects_tampered_silver(tmp_path):
    config, bronze, silver = context(tmp_path)
    bronze.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z")
    result = SeguridadSocialTransform(config).run(GREEN)
    Path(result["paths"]["pensiones"]).write_bytes(b"alterado")

    with pytest.raises(ValueError, match="no coincide con el manifiesto"):
        PensionesIndicadores(config).run()
