from datetime import date

import pandas as pd
import pytest

from src.transform.seguridad_social.afiliados_parser import AfiliadosParser
from fakes.ine_payloads import load_config
from fakes.seguridad_social_workbooks import afiliados_rows, afiliados_total, grid, months


def parser():
    return AfiliadosParser(load_config()["silver"]["seguridad_social"]["afiliados"])


def test_month_names_become_year_month_and_last_day_of_month():
    frame = parser().parse(grid(afiliados_rows(months("2016-01", "2016-12"))))

    assert frame["anyo"].tolist() == [2016] * 12
    assert frame["mes"].tolist() == list(range(1, 13))
    assert frame.loc[1, "fecha_referencia"] == date(2016, 2, 29)
    assert frame.loc[11, "fecha_referencia"] == date(2016, 12, 31)
    assert frame.loc[0, "periodo_original"] == "Enero 2016"
    assert frame["total_afiliados"].tolist() == [afiliados_total(2016, month) for month in range(1, 13)]


def test_irregular_spacing_and_abbreviations_are_accepted():
    rows = afiliados_rows([(1985, 2), (1985, 9)], values={("label", 1985, 2): "Febrero  1985", ("label", 1985, 9): "set 1985"})

    frame = parser().parse(grid(rows))

    assert frame["periodo_original"].tolist() == ["Febrero 1985", "set 1985"]
    assert frame["mes"].tolist() == [2, 9]


def test_footnotes_and_blank_rows_are_ignored():
    rows = afiliados_rows(months("2020-01", "2020-03"))
    rows.insert(4, [None])

    frame = parser().parse(grid(rows))

    assert len(frame) == 3


def test_total_column_is_located_by_header_not_by_position():
    rows = [[None] + row for row in afiliados_rows(months("2020-01", "2020-02"))]

    frame = parser().parse(grid(rows))

    assert frame["total_afiliados"].tolist() == [afiliados_total(2020, 1), afiliados_total(2020, 2)]


def test_missing_value_is_kept_as_null_for_quality_to_reject():
    frame = parser().parse(grid(afiliados_rows([(2020, 1)], values={(2020, 1): None})))

    assert frame["total_afiliados"].isna().all()


def test_unknown_month_is_an_error():
    with pytest.raises(ValueError, match="mes desconocido en 'Trimestre 2020'"):
        parser().parse(grid(afiliados_rows([(2020, 1)], values={("label", 2020, 1): "Trimestre 2020"})))


def test_missing_total_header_is_an_error():
    with pytest.raises(ValueError, match="no tiene el encabezado 'TOTAL SISTEMA'"):
        parser().parse(grid(afiliados_rows(total_header="TOTAL GENERAL")))


def test_non_numeric_value_is_an_error():
    with pytest.raises(ValueError, match="valor no numérico"):
        parser().parse(grid(afiliados_rows([(2020, 1)], values={(2020, 1): "n.d."})))


def test_sheet_without_periods_is_an_error():
    with pytest.raises(ValueError, match="no contiene filas con periodo"):
        parser().parse(grid(afiliados_rows([])))


def test_unexpected_format_is_an_error():
    with pytest.raises(ValueError, match="no tiene el encabezado 'Periodo'"):
        parser().parse(pd.DataFrame([["a", "b"], [1, 2]], dtype=object))
