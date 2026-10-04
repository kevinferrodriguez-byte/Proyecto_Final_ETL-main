from datetime import date, datetime, timezone

import pytest

from src.indicators.kpi_ratio import RatioCotizantesPensionistas
from fakes.fake_seguridad_social import afiliados_frame, pensiones_frame
from fakes.ine_payloads import load_config
from fakes.seguridad_social_workbooks import afiliados_rows, afiliados_total, months, pension_row, pension_total, pensiones_rows

GENERATED_AT = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)


def compute(afiliados=None, pensiones=None):
    ratio = RatioCotizantesPensionistas(load_config()["indicadores"]["pensiones"], "Seguridad Social")
    afiliados = afiliados_frame() if afiliados is None else afiliados
    pensiones = pensiones_frame() if pensiones is None else pensiones
    return ratio.compute(afiliados, pensiones, "silver_seguridad_social_1", GENERATED_AT)


def test_ratio_is_december_affiliates_over_december_pensions():
    frame = compute()["frame"]
    row = frame[frame["anyo"].eq(2020)].iloc[0]

    assert frame["anyo"].tolist() == list(range(2016, 2026))
    assert row["total_afiliados"] == afiliados_total(2020, 12)
    assert row["total_pensiones"] == pension_total(2020)
    assert row["ratio_cotizantes_pensionistas"] == pytest.approx(afiliados_total(2020, 12) / pension_total(2020))
    assert row["fecha_referencia_afiliados"] == date(2020, 12, 31)
    assert row["fecha_referencia_pensiones"] == date(2020, 12, 1)
    assert set(frame["metodologia_ratio"]) == {"stock_diciembre"}
    assert set(frame["mes_referencia"]) == {12}
    assert set(frame["silver_run_id"]) == {"silver_seguridad_social_1"}


def test_other_months_are_never_averaged_into_the_ratio():
    afiliados = afiliados_frame()
    afiliados.loc[afiliados["mes"].ne(12), "total_afiliados"] = 1

    frame = compute(afiliados=afiliados)["frame"]

    assert frame.loc[frame["anyo"].eq(2025), "total_afiliados"].item() == afiliados_total(2025, 12)


def test_annual_december_row_is_preferred_over_monthly_december_row():
    rows = pensiones_rows(overrides={("mensual", 2025, 12): pension_row(None, "Dic", pension_total(2025) + 5)})

    frame = compute(pensiones=pensiones_frame(rows))["frame"]

    row = frame[frame["anyo"].eq(2025)].iloc[0]
    assert row["tipo_corte_pensiones"] == "anual"
    assert row["total_pensiones"] == pension_total(2025)


def test_monthly_december_is_used_when_no_annual_row_exists():
    pensiones = pensiones_frame(pensiones_rows(annual_years=range(2016, 2025)))

    frame = compute(pensiones=pensiones)["frame"]

    row = frame[frame["anyo"].eq(2025)].iloc[0]
    assert row["tipo_corte_pensiones"] == "mensual"
    assert row["fecha_referencia_pensiones"] == date(2025, 12, 1)


def test_years_without_counterpart_are_reported_and_excluded():
    afiliados = afiliados_frame(afiliados_rows(months("2014-01", "2026-08")))
    pensiones = pensiones_frame(pensiones_rows(annual_years=range(2016, 2026), monthly=months("2025-01", "2025-12"), unpublished=[]))
    afiliados = afiliados[~afiliados["anyo"].eq(2019)]

    computed = compute(afiliados=afiliados, pensiones=pensiones)

    assert 2019 not in computed["frame"]["anyo"].tolist()
    assert 2026 not in computed["frame"]["anyo"].tolist()
    assert computed["unmatched"] == {"anyos_afiliados_sin_pensiones": [2014, 2015], "anyos_pensiones_sin_afiliados": [2019]}


def test_zero_denominator_produces_null_ratio_instead_of_infinity():
    pensiones = pensiones_frame()
    pensiones.loc[pensiones["tipo_corte"].eq("anual") & pensiones["anyo"].eq(2017), "total_pensiones"] = 0

    frame = compute(pensiones=pensiones)["frame"]

    assert frame.loc[frame["anyo"].eq(2017), "ratio_cotizantes_pensionistas"].isna().all()


def test_mixed_data_states_are_rejected():
    pensiones = pensiones_frame()
    pensiones["estado_dato"] = "provisional"

    with pytest.raises(ValueError, match="mezclaría estados"):
        compute(pensiones=pensiones)
