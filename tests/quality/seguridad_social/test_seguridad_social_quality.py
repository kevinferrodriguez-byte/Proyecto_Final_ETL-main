from datetime import date
from pathlib import Path

import pandas as pd

from src.quality.quality_evaluation import QualityEvaluation
from src.quality.seguridad_social_quality import SeguridadSocialQuality
from fakes.fake_seguridad_social import afiliados_frame, pensiones_frame, seguridad_social_config
from fakes.seguridad_social_workbooks import months, pension_row, pension_total, pensiones_rows

TODAY = date(2026, 9, 29)


def quality():
    config = seguridad_social_config(Path("sin_uso"))
    return SeguridadSocialQuality(config["silver"]["seguridad_social"], config["quality"])


def results(evaluation):
    return {rule["regla"]: rule["resultado"] for rule in evaluation.rules}


def failed(evaluation):
    return sorted(name for name, result in results(evaluation).items() if result == "falla")


def test_valid_frames_pass_every_rule_and_report_coverage():
    evaluation = quality().evaluate(afiliados_frame(), pensiones_frame(), QualityEvaluation(), TODAY)

    assert evaluation.passed(), evaluation.problems()
    assert len(evaluation.rules) == 8 + 14
    assert all(name.startswith(("afiliados.", "pensiones.")) for name in results(evaluation))
    assert evaluation.metrics["afiliados"]["completitud_temporal"]["completitud"] == 1.0
    assert evaluation.metrics["pensiones"]["completitud_temporal_anual"]["presentes"] == 10
    assert evaluation.metrics["pensiones"]["anyos_anual_contrastados_con_mensual"] == [2025]


def test_null_total_is_rejected():
    frame = afiliados_frame()
    frame.loc[3, "total_afiliados"] = pd.NA

    assert failed(quality().evaluate_afiliados(frame, TODAY)) == ["valores_no_nulos"]


def test_non_positive_and_negative_values_are_rejected():
    afiliados = afiliados_frame()
    afiliados.loc[0, "total_afiliados"] = 0
    pensiones = pensiones_frame()
    pensiones.loc[0, "pensiones_favor_familiar"] += pensiones.loc[0, "pensiones_orfandad"] + 1
    pensiones.loc[0, "pensiones_orfandad"] = -1

    assert failed(quality().evaluate_afiliados(afiliados, TODAY)) == ["valores_positivos"]
    assert failed(quality().evaluate_pensiones(pensiones, TODAY)) == ["clases_no_negativas"]


def test_duplicated_period_is_rejected():
    frame = afiliados_frame()
    frame = pd.concat([frame, frame.iloc[[5]]], ignore_index=True)

    assert failed(quality().evaluate_afiliados(frame, TODAY)) == ["clave_unica"]


def test_invalid_month_and_incoherent_date_are_rejected():
    frame = afiliados_frame()
    frame.loc[0, "mes"] = 13

    assert failed(quality().evaluate_afiliados(frame, TODAY)) == ["fechas_coherentes", "mes_valido"]


def test_future_dates_are_rejected():
    assert failed(quality().evaluate_afiliados(afiliados_frame(), date(2026, 8, 30))) == ["fechas_coherentes"]


def test_temporal_gap_within_tolerance_passes_but_is_reported():
    frame = afiliados_frame()
    frame = frame[~(frame["anyo"].eq(2018) & frame["mes"].eq(5))]

    evaluation = quality().evaluate_afiliados(frame, TODAY)

    assert evaluation.passed()
    assert evaluation.metrics["completitud_temporal"]["faltantes"] == ["2018-05"]


def test_temporal_completeness_below_threshold_is_rejected_even_without_nulls():
    frame = afiliados_frame()
    frame = frame[~frame["anyo"].isin([2018, 2019])]

    evaluation = quality().evaluate_afiliados(frame, TODAY)

    assert failed(evaluation) == ["completitud_temporal"]
    assert frame.isna().sum().sum() == 0
    assert evaluation.metrics["completitud_temporal"]["completitud"] < 0.95


def test_schema_type_error_skips_the_remaining_rules():
    frame = afiliados_frame().astype({"total_afiliados": "float64"})

    evaluation = quality().evaluate_afiliados(frame, TODAY)

    assert failed(evaluation) == ["esquema"]
    assert {rule["resultado"] for rule in evaluation.rules[1:]} == {"no_evaluada"}


def test_class_larger_than_total_and_sum_mismatch_are_rejected():
    frame = pensiones_frame()
    frame.loc[0, "pensiones_jubilacion"] = frame.loc[0, "total_pensiones"] + 1

    assert failed(quality().evaluate_pensiones(frame, TODAY)) == ["clases_no_superan_total", "clases_suman_total"]


def test_annual_value_must_match_december_monthly_value():
    total = pension_total(2025) + 7
    rows = pensiones_rows(overrides={("anual", 2025): pension_row(2025, None, total)})
    frame = pensiones_frame(rows)

    assert failed(quality().evaluate_pensiones(frame, TODAY)) == ["anual_igual_a_mensual_de_referencia"]


def test_annual_row_outside_reference_month_is_rejected():
    frame = pensiones_frame()
    annual = frame["tipo_corte"].eq("anual") & frame["anyo"].eq(2016)
    frame.loc[annual, "mes"] = 6
    frame.loc[annual, "fecha_referencia"] = date(2016, 6, 1)

    assert failed(quality().evaluate_pensiones(frame, TODAY)) == ["corte_anual_en_mes_de_referencia"]


def test_missing_monthly_coverage_is_rejected():
    frame = pensiones_frame(pensiones_rows(monthly=months("2025-01", "2025-12"), unpublished=[]))

    assert failed(quality().evaluate_pensiones(frame, TODAY)) == ["completitud_temporal_mensual"]


def test_missing_annual_coverage_is_rejected():
    frame = pensiones_frame(pensiones_rows(annual_years=range(2016, 2024)))

    assert failed(quality().evaluate_pensiones(frame, TODAY)) == ["completitud_temporal_anual"]


def test_valid_amounts_pass_and_are_reported_as_a_third_dataset():
    from fakes.fake_seguridad_social import importe_frame

    evaluation = quality().evaluate(afiliados_frame(), pensiones_frame(), QualityEvaluation(), TODAY, importe_frame())

    assert evaluation.passed(), evaluation.problems()
    assert sum(name.startswith("importe.") for name in results(evaluation)) == 10


def test_amounts_whose_classes_do_not_add_up_are_rejected():
    from fakes.fake_seguridad_social import importe_frame

    amounts = importe_frame()
    amounts.loc[0, "importe_total"] += 5.0

    evaluation = quality().evaluate(afiliados_frame(), pensiones_frame(), QualityEvaluation(), TODAY, amounts)

    assert failed(evaluation) == ["importe.clases_suman_total"]


def test_amounts_with_periods_missing_from_the_counts_are_rejected():
    from fakes.fake_seguridad_social import importe_frame

    amounts = importe_frame().iloc[1:].reset_index(drop=True)

    evaluation = quality().evaluate(afiliados_frame(), pensiones_frame(), QualityEvaluation(), TODAY, amounts)

    assert "importe.periodos_iguales_a_numero" in failed(evaluation)
