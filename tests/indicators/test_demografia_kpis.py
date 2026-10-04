from datetime import datetime, timezone

import pytest

from src.indicators.demografia_kpis import DemografiaKpis
from src.indicators.kpi_schema import KpiSchema
from fakes.ine_payloads import load_config
from fakes.silver_samples import population, silver_frame, vital

GENERATED_AT = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def compute(rows):
    return DemografiaKpis(load_config()["indicadores"]["demografia"]).compute(silver_frame(rows), "silver_1", GENERATED_AT)


def kpi(frame, indicator, year, escenario="observado"):
    selected = frame[frame["indicador"].eq(indicator) & frame["anyo"].eq(year) & frame["escenario"].eq(escenario)]
    assert len(selected) == 1
    return selected.iloc[0]


def test_known_example_gives_expected_indicators():
    frame = compute(population(2025))["frame"]

    assert kpi(frame, "indice_envejecimiento", 2025)["valor"] == pytest.approx(100.0)
    assert kpi(frame, "tasa_dependencia", 2025)["valor"] == pytest.approx(50.0)
    assert kpi(frame, "tasa_dependencia_mayores", 2025)["valor"] == pytest.approx(25.0)
    assert set(frame["unidad"]) == {"porcentaje"}
    KpiSchema().validate(frame)


def test_boundary_ages_fall_in_numeric_groups_and_open_interval_counts_as_elderly():
    groups = compute(population(2025))["age_groups"].iloc[0]

    assert groups["menores_16"] == 15.0
    assert groups["activos_16_64"] == 60.0
    assert groups["mayores_65"] == 15.0
    assert groups["filas_sin_grupo"] == 0
    assert groups["total_detalle"] == 90.0


def test_control_rows_and_sex_breakdown_are_ignored():
    rows = population(2025) + population(2025, sexo="mujeres", ages=[(0, 0, 999.0), (70, 70, 999.0)])

    frame = compute(rows)["frame"]

    assert kpi(frame, "indice_envejecimiento", 2025)["valor"] == pytest.approx(100.0)


def test_scenarios_are_mapped_to_kr_scenarios():
    rows = (
        population(2025)
        + population(2050, "central")
        + population(2050, "fecundidad_y_saldo_migratorio_altos")
        + population(2050, "fecundidad_y_saldo_migratorio_bajos")
        + population(2050, "saldo_migratorio_nulo")
    )

    frame = compute(rows)["frame"]
    mapping = frame.drop_duplicates("escenario").set_index("escenario")["escenario_kr"].to_dict()

    assert mapping == {
        "observado": "observado",
        "central": "base",
        "fecundidad_y_saldo_migratorio_altos": "optimista",
        "fecundidad_y_saldo_migratorio_bajos": "pesimista",
        "saldo_migratorio_nulo": "sensibilidad",
    }
    assert set(frame.loc[frame["escenario"].ne("observado"), "estado_dato"]) == {"proyectado"}


def test_natural_balance_is_births_minus_deaths_and_never_projected():
    frame = compute(population(2025) + population(2050, "central") + vital(2024, 318005.0, 436118.0))["frame"]
    balance = frame[frame["indicador"].eq("saldo_vegetativo")]

    assert balance[["anyo", "valor", "unidad", "estado_dato"]].values.tolist() == [[2024, -118113.0, "personas", "observado"]]


def test_zero_denominator_yields_no_value_instead_of_dividing():
    computed = compute(population(2025, ages=[(30, 30, 50.0), (70, 70, 10.0)]))

    assert computed["age_groups"]["menores_16"].iloc[0] == 0.0
    assert kpi(computed["frame"], "indice_envejecimiento", 2025)["valor"] != kpi(computed["frame"], "indice_envejecimiento", 2025)["valor"]
    assert kpi(computed["frame"], "tasa_dependencia", 2025)["valor"] == pytest.approx(20.0)


def test_unexpected_open_interval_below_65_is_left_without_group():
    groups = compute(population(2025, ages=[(0, 0, 10.0), (16, 16, 20.0), (60, None, 5.0)]))["age_groups"].iloc[0]

    assert groups["filas_sin_grupo"] == 1
    assert groups["menores_16"] + groups["activos_16_64"] + groups["mayores_65"] == 30.0
    assert groups["total_detalle"] == 35.0
