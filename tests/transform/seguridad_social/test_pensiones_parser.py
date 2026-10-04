from datetime import date

import pytest

from src.transform.seguridad_social.pensiones_parser import PensionesParser
from fakes.ine_payloads import load_config
from fakes.seguridad_social_workbooks import PENSION_HEADER, grid, months, pension_classes, pension_row, pension_total, pensiones_rows

CLASSES = ["pensiones_incapacidad_permanente", "pensiones_jubilacion", "pensiones_viudedad", "pensiones_orfandad", "pensiones_favor_familiar"]


def parse(rows):
    return PensionesParser(load_config()["silver"]["seguridad_social"]["pensiones"]).parse(grid(rows))


def test_annual_rows_are_december_per_source_note_and_marked_as_annual():
    frame = parse(pensiones_rows())["frame"]
    annual = frame[frame["tipo_corte"].eq("anual")]

    assert annual["anyo"].tolist() == list(range(2016, 2026))
    assert annual["mes"].unique().tolist() == [12]
    assert annual.iloc[0]["fecha_referencia"] == date(2016, 12, 1)
    assert annual.iloc[0]["periodo_original"] == "2016"
    assert annual.iloc[0]["total_pensiones"] == pension_total(2016)
    assert annual.iloc[0][CLASSES].tolist() == pension_classes(pension_total(2016))


def test_monthly_rows_carry_the_year_forward_and_use_day_one():
    frame = parse(pensiones_rows())["frame"]
    monthly = frame[frame["tipo_corte"].eq("mensual")]

    assert list(zip(monthly["anyo"], monthly["mes"])) == months("2025-01", "2026-09")
    assert monthly.iloc[1]["periodo_original"] == "2025 Feb"
    assert monthly.iloc[12]["fecha_referencia"] == date(2026, 1, 1)
    assert monthly.iloc[12]["total_pensiones"] == pension_total(2026, 1)


def test_percentage_block_after_end_marker_is_not_read():
    frame = parse(pensiones_rows())["frame"]

    assert len(frame) == 10 + 21
    assert frame["total_pensiones"].min() > 1_000_000


def test_months_without_values_are_reported_as_unpublished():
    parsed = parse(pensiones_rows())

    assert parsed["unpublished"] == ["2026 Oct", "2026 Nov", "2026 Dic"]


def test_only_monthly_rows_are_accepted_without_annual_block():
    frame = parse(pensiones_rows(annual_years=[]))["frame"]

    assert frame["tipo_corte"].unique().tolist() == ["mensual"]


def test_annual_rows_are_not_assigned_to_december_without_the_source_note():
    with pytest.raises(ValueError, match="no incluye la nota 'Datos anuales a diciembre de cada año.'"):
        parse(pensiones_rows(note=None))


def test_unknown_month_is_an_error():
    rows = pensiones_rows(overrides={("mensual", 2025, 3): pension_row(None, "Trim", pension_total(2025, 3))})

    with pytest.raises(ValueError, match="mes desconocido 'Trim'"):
        parse(rows)


def test_month_without_year_is_an_error():
    rows = pensiones_rows(annual_years=[], overrides={("mensual", 2025, 1): pension_row(None, "Ene", pension_total(2025, 1))})

    with pytest.raises(ValueError, match="mes sin año"):
        parse(rows)


def test_invalid_year_is_an_error():
    rows = pensiones_rows(overrides={("anual", 2016): pension_row("2016*", None, pension_total(2016))})

    with pytest.raises(ValueError, match="año no válido"):
        parse(rows)


def test_missing_expected_column_is_an_error():
    header = [label if label != "VIUDEDAD" else None for label in PENSION_HEADER]

    with pytest.raises(ValueError, match="no tiene las columnas esperadas: VIUDEDAD"):
        parse(pensiones_rows(header=header))


def test_unexpected_column_is_an_error():
    header = PENSION_HEADER + ["SOVI"]

    with pytest.raises(ValueError, match="columnas no previstas: SOVI"):
        parse(pensiones_rows(header=header))


def test_non_numeric_value_is_an_error():
    rows = pensiones_rows(overrides={("anual", 2017): [2017, None, "n.d.", 1, 1, 1, 1, 5]})

    with pytest.raises(ValueError, match="valor no numérico"):
        parse(rows)


def test_sheet_without_periods_is_an_error():
    with pytest.raises(ValueError, match="no contiene filas de periodo"):
        parse(pensiones_rows(annual_years=[], monthly=[], unpublished=[]))
