from datetime import datetime, timezone

import pandas as pd

from src.quality.kpi_quality import KpiQuality
from src.quality.quality_evaluation import QualityEvaluation
from src.indicators.demografia_kpis import DemografiaKpis
from fakes.ine_payloads import load_config
from fakes.silver_samples import population, silver_frame, vital

GENERATED_AT = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def evaluate(rows, adjust=None):
    config = load_config()
    computed = DemografiaKpis(config["indicadores"]["demografia"]).compute(silver_frame(rows), "silver_1", GENERATED_AT)
    if adjust is not None:
        computed = adjust(computed)
    evaluation = QualityEvaluation()
    KpiQuality(config["indicadores"]["demografia"], config["quality"]["max_null_percentage"]).evaluate(computed, evaluation)
    return {rule["regla"]: rule["resultado"] for rule in evaluation.rules}, evaluation


def test_clean_kpis_pass_every_rule():
    results, evaluation = evaluate(population(2025) + population(2050, "central") + vital(2024, 10.0, 12.0))

    assert set(results.values()) == {"cumple"}
    assert evaluation.passed()
    assert evaluation.metrics["filas_por_indicador_y_escenario_kr"]["saldo_vegetativo|observado"] == 1


def test_zero_denominator_is_rejected():
    results, evaluation = evaluate(population(2025, ages=[(30, 30, 50.0), (70, 70, 10.0)]))

    assert results["denominadores_positivos"] == "falla"
    assert results["valores_no_nulos"] == "falla"
    assert any("división por cero rechazada" in problem for problem in evaluation.problems())


def test_unexpected_ages_are_rejected():
    results, evaluation = evaluate(population(2025, ages=[(0, 0, 10.0), (16, 16, 20.0), (60, None, 5.0)]))

    assert results["edades_asignadas"] == "falla"
    assert results["grupos_suman_total"] == "falla"
    assert not evaluation.passed()


def test_negative_population_is_rejected():
    results, evaluation = evaluate(population(2025, ages=[(0, 0, 10.0), (16, 16, 20.0), (70, 70, -1.0)]))

    assert results["poblacion_no_negativa"] == "falla"


def test_incomplete_vital_statistics_are_rejected():
    results, evaluation = evaluate(population(2025) + vital(2024, 10.0, None))

    assert results["eventos_completos"] == "falla"


def test_observed_and_projected_sharing_a_key_are_rejected():
    results, evaluation = evaluate(population(2025) + population(2025, "central"))

    assert results["sin_mezcla_observado_proyectado"] == "falla"


def test_duplicated_kpi_key_is_rejected():
    def duplicate(computed):
        computed["frame"] = pd.concat([computed["frame"], computed["frame"].iloc[:1]], ignore_index=True)
        return computed

    results, evaluation = evaluate(population(2025), duplicate)

    assert results["clave_unica"] == "falla"


def test_schema_failure_skips_business_rules():
    def break_schema(computed):
        computed["frame"] = computed["frame"].drop(columns=["escenario_kr"])
        return computed

    results, evaluation = evaluate(population(2025), break_schema)

    assert results["esquema"] == "falla"
    assert {result for rule, result in results.items() if rule != "esquema"} == {"no_evaluada"}
