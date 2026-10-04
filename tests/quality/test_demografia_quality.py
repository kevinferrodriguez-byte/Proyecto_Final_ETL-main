from datetime import date

import pandas as pd
import pyarrow as pa
import pytest

from src.quality.demografia_quality import DemografiaQuality
from fakes.demografia_rows import all_ages, frame_from, open_interval, simple_age
from fakes.ine_payloads import load_config


def quality():
    config = load_config()
    return DemografiaQuality(config["silver"]["validation"], config["quality"]["max_null_percentage"])


def no_homologation():
    return pd.DataFrame(columns=["tabla_id", "metrica", "fecha_referencia", "sexo", "escenario", "components", "published"])


def age_rows(table_id, fecha, detail_values, total, row=None):
    base = {"tabla_id": table_id, "fecha_referencia": fecha, "anyo": fecha.year}
    base.update(row or {})
    rows = [simple_age(age, valor, base) for age, valor in enumerate(detail_values[:-1])]
    rows.append(open_interval(len(detail_values) - 1, detail_values[-1], base))
    rows.append(all_ages(total, base))
    return rows


def projected(scenario="central"):
    return {"estado_dato": "proyectado", "escenario": scenario}


def test_clean_frame_passes():
    frame = frame_from(age_rows("56934", date(2020, 1, 1), [10.0, 5.0], 15.0))

    assert quality().problems(frame, no_homologation()) == []


def test_56934_tolerates_up_to_16_people_before_july_2012():
    within = frame_from(age_rows("56934", date(1996, 1, 1), [10.0, 5.0], 31.0))
    beyond = frame_from(age_rows("56934", date(1996, 1, 1), [10.0, 5.0], 32.0))

    assert quality().problems(within, no_homologation()) == []
    assert any("no cuadran detalle" in problem for problem in quality().problems(beyond, no_homologation()))


def test_56934_requires_exact_totals_from_july_2012():
    frame = frame_from(age_rows("56934", date(2013, 1, 1), [10.0, 5.0], 16.0))

    problems = quality().problems(frame, no_homologation())

    assert len(problems) == 1 and "1 grupos no cuadran detalle" in problems[0]


def test_projections_require_exact_totals_with_float_epsilon_only():
    exact = frame_from(age_rows("36643", date(2030, 1, 1), [10.25, 5.5], 15.75 + 1e-9, projected()))
    off = frame_from(age_rows("36652", date(2030, 1, 1), [10.25, 5.5], 16.75, projected("fecundidad_alta")))

    assert quality().problems(exact, no_homologation()) == []
    assert any("no cuadran detalle" in problem for problem in quality().problems(off, no_homologation()))


def test_missing_total_for_a_group_is_reported():
    rows = age_rows("56934", date(2020, 1, 1), [10.0, 5.0], 15.0)[:-1]

    problems = quality().problems(frame_from(rows), no_homologation())

    assert any("sin pareja detalle/total" in problem for problem in problems)


def test_duplicated_business_key_is_reported():
    rows = age_rows("56934", date(2020, 1, 1), [10.0, 5.0], 15.0)
    rows.append(dict(rows[0], valor=11.0))

    problems = quality().problems(frame_from(rows), no_homologation())

    assert any("repiten la clave de negocio" in problem for problem in problems)


def test_observed_and_projected_rows_in_same_key_are_reported():
    observed = age_rows("56934", date(2026, 1, 1), [10.0, 5.0], 15.0)
    projection = age_rows("36643", date(2026, 1, 1), [10.0, 5.0], 15.0, projected())

    problems = quality().problems(frame_from(observed + projection), no_homologation())

    assert any("mezclan datos observados y proyectados" in problem for problem in problems)


def test_homologated_interval_must_match_its_components():
    homologation = pd.DataFrame(
        [
            {"tabla_id": "56934", "metrica": "poblacion", "fecha_referencia": date(2020, 1, 1), "sexo": "total", "escenario": "observado", "components": 17038.0, "published": 17038.0},
            {"tabla_id": "56934", "metrica": "poblacion", "fecha_referencia": date(2021, 1, 1), "sexo": "total", "escenario": "observado", "components": 17038.0, "published": 17040.0},
        ]
    )
    homologation["fecha_referencia"] = homologation["fecha_referencia"].astype(pd.ArrowDtype(pa.date32()))
    frame = frame_from(age_rows("56934", date(2020, 1, 1), [10.0, 5.0], 15.0))

    problems = quality().problems(frame, homologation)

    assert len(problems) == 1 and "1 grupos con tramo homologado distinto" in problems[0]


def test_null_values_are_reported():
    rows = age_rows("56934", date(2020, 1, 1), [10.0, 5.0], 15.0)
    rows.append({"tabla_id": "69758", "metrica": "saldo_migratorio_exterior", "tipo_edad": "total", "edad_max": None, "valor": None})

    problems = quality().problems(frame_from(rows), no_homologation())

    assert "1 filas sin valor" in problems


def test_schema_problems_are_reported_before_business_rules():
    frame = frame_from(age_rows("56934", date(2020, 1, 1), [10.0, 5.0], 15.0)).drop(columns=["escenario"])

    assert quality().problems(frame, no_homologation()) == ["faltan columnas: escenario"]


def test_validate_blocks_with_every_problem():
    rows = age_rows("56934", date(2013, 1, 1), [10.0, 5.0], 16.0)
    rows.append(dict(rows[0], valor=11.0))

    with pytest.raises(ValueError, match="Plata no supera las validaciones de calidad: .*repiten la clave.*no cuadran detalle"):
        quality().validate(frame_from(rows), no_homologation())
