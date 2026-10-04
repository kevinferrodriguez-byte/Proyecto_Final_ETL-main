from datetime import date, datetime, timezone

import pandas as pd

from src.quality.quality_evaluation import QualityEvaluation
from src.quality.seguridad_social_kpi_quality import SeguridadSocialKpiQuality
from src.indicators.kpi_ratio import RatioCotizantesPensionistas
from fakes.fake_seguridad_social import afiliados_frame, importe_frame, pensiones_frame
from fakes.ine_payloads import load_config


def computed():
    config = load_config()
    ratio = RatioCotizantesPensionistas(config["indicadores"]["pensiones"], "Seguridad Social")
    return ratio.compute(afiliados_frame(), pensiones_frame(), "silver_seguridad_social_1", datetime(2026, 9, 29, tzinfo=timezone.utc), importe_frame())


def evaluate(result):
    config = load_config()
    return SeguridadSocialKpiQuality(config["indicadores"]["pensiones"], config["quality"]).evaluate(result, QualityEvaluation())


def failed(evaluation):
    return sorted(rule["regla"] for rule in evaluation.rules if rule["resultado"] == "falla")


def test_valid_ratio_passes_every_rule():
    evaluation = evaluate(computed())

    assert evaluation.passed(), evaluation.problems()
    assert evaluation.metrics["cobertura_anual"]["anyos_con_ratio"] == list(range(2016, 2026))
    assert "anyos_afiliados_sin_pensiones" in evaluation.metrics


def test_zero_denominator_is_rejected():
    result = computed()
    frame = result["frame"]
    frame.loc[0, "total_pensiones"] = 0
    frame.loc[0, "ratio_cotizantes_pensionistas"] = float("nan")

    assert failed(evaluate(result)) == ["cobertura_anual", "denominadores_positivos", "fraccion_nulos", "valores_no_nulos"]


def test_non_positive_and_incoherent_ratio_is_rejected():
    result = computed()
    result["frame"].loc[1, "ratio_cotizantes_pensionistas"] = -1.0

    assert failed(evaluate(result)) == ["ratio_coherente", "ratio_positivo"]


def test_duplicated_year_is_rejected():
    result = computed()
    result["frame"] = pd.concat([result["frame"], result["frame"].iloc[[2]]], ignore_index=True)

    assert failed(evaluate(result)) == ["clave_unica"]


def test_numerator_from_another_month_breaks_methodology():
    result = computed()
    result["frame"].loc[3, "fecha_referencia_afiliados"] = date(2019, 6, 30)

    assert failed(evaluate(result)) == ["metodologia_homogenea"]


def test_missing_years_below_threshold_are_rejected():
    result = computed()
    result["frame"] = result["frame"][result["frame"]["anyo"].ge(2018)].reset_index(drop=True)

    evaluation = evaluate(result)

    assert failed(evaluation) == ["cobertura_anual"]
    assert evaluation.metrics["cobertura_anual"]["faltantes"] == [2016, 2017]


def test_schema_error_skips_the_remaining_rules():
    result = computed()
    result["frame"] = result["frame"].astype({"total_pensiones": "float64"})

    evaluation = evaluate(result)

    assert failed(evaluation) == ["esquema"]
    assert {rule["resultado"] for rule in evaluation.rules[1:]} == {"no_evaluada"}
