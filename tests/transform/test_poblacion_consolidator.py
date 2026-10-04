from datetime import date

import pytest

from src.quality.demografia_quality import DemografiaQuality
from src.transform.poblacion_consolidator import PoblacionConsolidator
from fakes.demografia_rows import frame_from
from fakes.ine_payloads import load_config


def consolidator():
    config = load_config()
    return PoblacionConsolidator(config["sources"]["ine"], config["silver"]["ine"])


def total_row(table_id, metrica, year, valor, row=None):
    record = {
        "tabla_id": table_id,
        "metrica": metrica,
        "fecha_referencia": date(year, 1, 1),
        "anyo": year,
        "tipo_edad": "total",
        "edad_max": None,
        "edad_etiqueta_original": "Todas las edades",
        "valor": valor,
    }
    record.update(row or {})
    return record


def test_quarterly_population_keeps_only_january_first():
    rows = [
        {"fecha_referencia": date(2024, 1, 1), "anyo": 2024},
        {"fecha_referencia": date(2024, 7, 1), "anyo": 2024},
        {"fecha_referencia": date(2024, 10, 1), "anyo": 2024},
    ]

    result = consolidator().consolidate(frame_from(rows))

    assert result["fecha_referencia"].tolist() == [date(2024, 1, 1)]


def test_annual_table_outside_reference_date_is_rejected():
    rows = [total_row("6566", "nacimientos", 2024, 1.0, {"fecha_referencia": date(2024, 7, 1)})]

    with pytest.raises(ValueError, match=r"Las tablas anuales \['6566'\]"):
        consolidator().consolidate(frame_from(rows))


def test_migration_series_switches_from_24309_to_69758_in_2021():
    rows = [
        total_row("24309", "saldo_migratorio_exterior", 2020, 100.0, {"unidad": "movimientos_migratorios"}),
        total_row("24309", "saldo_migratorio_exterior", 2021, 110.0, {"unidad": "movimientos_migratorios"}),
        total_row("69758", "saldo_migratorio_exterior", 2021, 120.0, {"unidad": "migraciones"}),
    ]

    result = consolidator().consolidate(frame_from(rows))

    assert result[["tabla_id", "anyo", "unidad"]].values.tolist() == [
        ["24309", 2020, "movimientos_migratorios"],
        ["69758", 2021, "migraciones"],
    ]


def test_central_scenario_of_36652_is_excluded_but_36643_central_is_kept():
    projected = {"estado_dato": "proyectado", "fecha_referencia": date(2030, 1, 1), "anyo": 2030}
    rows = [
        dict(projected, tabla_id="36643", escenario="central"),
        dict(projected, tabla_id="36652", escenario="central"),
        dict(projected, tabla_id="36652", escenario="fecundidad_alta"),
    ]

    result = consolidator().consolidate(frame_from(rows))

    assert result[["tabla_id", "escenario"]].values.tolist() == [["36643", "central"], ["36652", "fecundidad_alta"]]


def test_6566_identical_copies_are_deduplicated_regardless_of_order():
    births = total_row("6566", "nacimientos", 2024, 320000.0, {"codigo_serie": "MNP17544", "unidad": "nacimientos"})
    deaths = total_row("6566", "defunciones", 2024, 430000.0, {"codigo_serie": "MNP17542", "unidad": "defunciones"})
    first_order = consolidator().consolidate(frame_from([births, deaths, births, deaths, births, deaths]))
    second_order = consolidator().consolidate(frame_from([deaths, births, deaths, births, deaths, births]))

    assert sorted(first_order["metrica"]) == sorted(second_order["metrica"]) == ["defunciones", "nacimientos"]
    assert first_order.sort_values("metrica", ignore_index=True).equals(second_order.sort_values("metrica", ignore_index=True))


def test_6566_conflicting_copies_are_kept_and_rejected_by_quality():
    births = total_row("6566", "nacimientos", 2024, 320000.0, {"codigo_serie": "MNP17544", "unidad": "nacimientos"})
    conflicting = total_row("6566", "nacimientos", 2024, 320001.0, {"codigo_serie": "MNP17544", "unidad": "nacimientos"})

    result = consolidator().consolidate(frame_from([births, conflicting]))
    config = load_config()
    problems = DemografiaQuality(config["silver"]["validation"], config["quality"]["max_null_percentage"]).problems(result, result.iloc[0:0])

    assert len(result) == 2
    assert any("repiten la clave de negocio" in problem for problem in problems)


def test_duplicates_in_other_tables_are_not_silently_removed():
    row = total_row("69758", "saldo_migratorio_exterior", 2022, 5.0)

    result = consolidator().consolidate(frame_from([row, row]))

    assert len(result) == 2
