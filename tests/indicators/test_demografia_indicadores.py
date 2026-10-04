from pathlib import Path
import hashlib
import json

import pandas as pd
import pytest

from src.indicators.demografia_indicadores import DemografiaIndicadores
from src.indicators.kpi_schema import KpiSchema
from fakes.fake_silver import FakeSilver
from fakes.ine_payloads import load_config
from fakes.silver_samples import population, vital


def build(tmp_path):
    config = load_config()
    config["silver"]["manifests_path"] = str(tmp_path / "silver" / "manifests")
    config["indicadores"]["output_path"] = str(tmp_path / "gold")
    config["indicadores"]["demografia"]["manifests_path"] = str(tmp_path / "gold" / "manifests")
    return {"config": config, "silver": FakeSilver(tmp_path / "silver"), "gold": tmp_path / "gold"}


def read_report(gold):
    reports = list((gold / "manifests").glob("*.quality.json"))
    assert len(reports) == 1
    return json.loads(reports[0].read_text(encoding="utf-8"))


def test_run_writes_kpis_manifest_and_approved_report(tmp_path):
    context = build(tmp_path)
    context["silver"].publish(
        "silver_1",
        "2026-09-26T01:00:00.000000Z",
        population(2025) + population(2050, "central") + population(2050, "fecundidad_y_saldo_migratorio_bajos") + vital(2024, 10.0, 12.0),
    )

    result = DemografiaIndicadores(context["config"]).run()

    output = Path(result["path"])
    frame = pd.read_parquet(output)
    KpiSchema().validate(frame)
    assert output == context["gold"] / "kpis_demograficos.parquet"
    assert len(frame) == result["rows"] == 13
    assert set(frame["silver_run_id"]) == {"silver_1"}
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["silver_run_id"] == "silver_1"
    assert manifest["payloads"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    rows = {(row["indicador"], row["escenario_kr"]): row["filas"] for row in manifest["rows_by_indicator_and_scenario"]}
    assert rows[("indice_envejecimiento", "pesimista")] == 1
    assert rows[("saldo_vegetativo", "observado")] == 1
    report = read_report(context["gold"])
    assert report["estado"] == "aprobado"
    assert report["metricas"]["silver_run_id"] == "silver_1"
    assert {rule["resultado"] for rule in report["reglas"]} == {"cumple"}


def test_zero_denominator_rejects_run_and_reports_cause(tmp_path):
    context = build(tmp_path)
    context["silver"].publish("silver_1", "2026-09-26T01:00:00.000000Z", population(2025, ages=[(30, 30, 50.0), (70, 70, 10.0)]))

    with pytest.raises(ValueError, match="Oro indicadores demográficos no supera las validaciones de calidad: .*división por cero rechazada"):
        DemografiaIndicadores(context["config"]).run()

    assert not (context["gold"] / "kpis_demograficos.parquet").exists()
    report = read_report(context["gold"])
    assert report["estado"] == "rechazado"
    assert {rule["regla"]: rule["resultado"] for rule in report["reglas"]}["denominadores_positivos"] == "falla"


def test_missing_silver_input_is_reported(tmp_path):
    context = build(tmp_path)

    with pytest.raises(ValueError, match="No hay manifiestos de Plata completados"):
        DemografiaIndicadores(context["config"]).run()

    report = read_report(context["gold"])
    assert report["estado"] == "rechazado"
    assert "No hay manifiestos de Plata" in report["causa_rechazo"]
