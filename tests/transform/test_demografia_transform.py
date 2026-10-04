from pathlib import Path
import hashlib
import json

import pandas as pd
import pytest

from src.transform.demografia_schema import DemografiaSchema
from src.transform.demografia_transform import DemografiaTransform
from fakes.fake_bronze import FakeBronze, minimal_payloads
from fakes.ine_payloads import load_config

GREEN = {"ok": True}


def build(tmp_path):
    bronze = FakeBronze(tmp_path / "bronze" / "ine")
    config = load_config()
    config["sources"]["ine"]["storage"] = bronze.storage_config()
    config["paths"]["silver"] = str(tmp_path / "silver")
    config["silver"]["manifests_path"] = str(tmp_path / "silver" / "manifests")
    config["silver"]["ine"]["homologated_top_age"] = 3
    return {"bronze": bronze, "config": config, "silver": tmp_path / "silver"}


def read_single_report(silver):
    reports = list((silver / "manifests").glob("*.quality.json"))
    assert len(reports) == 1
    return json.loads(reports[0].read_text(encoding="utf-8"))


def test_run_writes_validated_parquet_and_silver_manifest(tmp_path):
    context = build(tmp_path)
    context["bronze"].run("ine_1", "2026-09-26T01:00:00.000000Z", minimal_payloads())

    result = DemografiaTransform(context["config"]).run(GREEN)

    output = Path(result["path"])
    frame = pd.read_parquet(output)
    DemografiaSchema().validate(frame)
    assert output == context["silver"] / "stg_poblacion_anual.parquet"
    assert result["rows"] == len(frame) == 26
    assert set(frame["run_id"]) == {"ine_1"}
    assert set(frame["metrica"]) == {"poblacion", "nacimientos", "defunciones", "saldo_migratorio_exterior", "indicador_coyuntural_fecundidad", "esperanza_vida_nacimiento", "esperanza_vida_65"}
    assert all(fecha.month == 1 and fecha.day == 1 for fecha in frame.loc[frame["tabla_id"].eq("56934"), "fecha_referencia"])
    assert not (frame["tabla_id"].eq("36652") & frame["escenario"].eq("central")).any()
    assert frame.loc[frame["metrica"].eq("saldo_migratorio_exterior"), ["tabla_id", "anyo", "unidad"]].values.tolist() == [
        ["24309", 2020, "movimientos_migratorios"],
        ["69758", 2021, "migraciones"],
    ]
    assert frame["metrica"].isin(["nacimientos", "defunciones"]).sum() == 2

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completada"
    assert manifest["bronze_run_ids"] == ["ine_1"]
    assert len(manifest["bronze_inputs"]) == 13
    assert manifest["payloads"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert manifest["payloads"][0]["rows"] == 26
    rows = {(row["tabla_id"], row["metrica"], row["escenario"]): row["filas"] for row in manifest["rows_summary"]["por_tabla_metrica_escenario"]}
    assert rows[("36652", "poblacion", "fecundidad_alta")] == 5
    assert ("36652", "poblacion", "central") not in rows

    report = read_single_report(context["silver"])
    assert Path(result["quality_report_path"]).name == f"{manifest['run_id']}.quality.json" == manifest["quality_report"]
    assert report["estado"] == "aprobado" and report["causa_rechazo"] is None
    assert {rule["resultado"] for rule in report["reglas"]} == {"cumple"}
    assert {rule["regla"] for rule in report["reglas"]} >= {"esquema", "no_negativos", "fraccion_nulos", "totales_por_edad", "clave_unica"}
    assert report["metricas"]["filas_por_metrica"]["poblacion"] == 15


def test_run_uses_latest_completed_bronze_run(tmp_path):
    context = build(tmp_path)
    context["bronze"].run("ine_1", "2026-09-26T01:00:00.000000Z", minimal_payloads())
    context["bronze"].run("ine_2", "2026-09-26T02:00:00.000000Z", minimal_payloads(migration_2021=-999.0))

    result = DemografiaTransform(context["config"]).run(GREEN)

    frame = pd.read_parquet(result["path"])
    assert set(frame["run_id"]) == {"ine_2"}
    assert frame.loc[frame["tabla_id"].eq("69758"), "valor"].tolist() == [-999.0]


def test_run_refuses_bronze_without_green_integrity(tmp_path):
    context = build(tmp_path)
    context["bronze"].run("ine_1", "2026-09-26T01:00:00.000000Z", minimal_payloads())

    with pytest.raises(RuntimeError, match="integridad de Bronce no está en verde"):
        DemografiaTransform(context["config"]).run({"ok": False})

    assert not (context["silver"] / "stg_poblacion_anual.parquet").exists()
    report = read_single_report(context["silver"])
    assert report["estado"] == "rechazado"
    assert [rule["resultado"] for rule in report["reglas"] if rule["regla"] == "integridad_bronce"] == ["falla"]


def test_failed_validation_blocks_writing(tmp_path):
    context = build(tmp_path)
    payloads = minimal_payloads()
    payloads[("36643", "total_edad")][0]["Data"][0]["Valor"] = 35.0
    context["bronze"].run("ine_1", "2026-09-26T01:00:00.000000Z", payloads)

    with pytest.raises(ValueError, match="no cuadran detalle con 'Todas las edades'"):
        DemografiaTransform(context["config"]).run(GREEN)

    assert not (context["silver"] / "stg_poblacion_anual.parquet").exists()
    assert not list((context["silver"] / "manifests").glob("*.manifest.json"))
    report = read_single_report(context["silver"])
    assert report["estado"] == "rechazado"
    assert "no cuadran detalle" in report["causa_rechazo"]
    assert {rule["regla"]: rule["resultado"] for rule in report["reglas"]}["totales_por_edad"] == "falla"
    assert report["metricas"]["filas"] == 26


def test_unexpected_age_label_rejects_run_and_writes_report(tmp_path):
    context = build(tmp_path)
    payloads = minimal_payloads()
    payloads[("56934", "detalle")][0]["MetaData"][3]["Nombre"] = "0 meses"
    context["bronze"].run("ine_1", "2026-09-26T01:00:00.000000Z", payloads)

    with pytest.raises(ValueError, match="Etiquetas de edad no reconocidas como simple.*0 meses"):
        DemografiaTransform(context["config"]).run(GREEN)

    report = read_single_report(context["silver"])
    assert report["estado"] == "rechazado"
    assert "0 meses" in report["causa_rechazo"]
    assert not (context["silver"] / "stg_poblacion_anual.parquet").exists()
