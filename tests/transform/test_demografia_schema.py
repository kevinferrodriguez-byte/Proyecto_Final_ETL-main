import pandas as pd
import pytest

from src.transform.demografia_schema import DemografiaSchema
from fakes.demografia_rows import valid_frame

EXPECTED_COLUMNS = [
    "fuente",
    "tabla_id",
    "consulta",
    "run_id",
    "codigo_serie",
    "fecha_referencia",
    "anyo",
    "territorio",
    "sexo",
    "edad_min",
    "edad_max",
    "edad_etiqueta_original",
    "tipo_edad",
    "metrica",
    "valor",
    "unidad",
    "estado_dato",
    "escenario",
    "es_control",
]


def test_schema_declares_ordered_snake_case_columns():
    assert DemografiaSchema().columns() == EXPECTED_COLUMNS


def test_valid_long_frame_and_empty_frame_pass():
    schema = DemografiaSchema()

    schema.validate(valid_frame())
    schema.validate(schema.empty())

    assert schema.problems(valid_frame()) == []


def test_open_interval_and_total_accept_null_edad_max():
    frame = valid_frame()

    assert frame.loc[frame["tipo_edad"] != "simple", "edad_max"].isna().all()
    DemografiaSchema().validate(frame)


def test_missing_column_is_rejected():
    frame = valid_frame().drop(columns=["run_id"])

    with pytest.raises(ValueError, match="faltan columnas: run_id"):
        DemografiaSchema().validate(frame)


def test_unexpected_column_is_rejected():
    frame = valid_frame().assign(comentario="x")

    with pytest.raises(ValueError, match="columnas no previstas: comentario"):
        DemografiaSchema().validate(frame)


def test_wrong_types_are_rejected():
    frame = valid_frame()
    frame["anyo"] = frame["anyo"].astype("float64")
    frame["fecha_referencia"] = frame["fecha_referencia"].astype("string")
    frame["es_control"] = frame["es_control"].astype("int64")

    problems = DemografiaSchema().problems(frame)

    assert len(problems) == 3
    assert any(problem.startswith("la columna anyo tiene tipo float64; se esperaba int64") for problem in problems)
    assert any(problem.startswith("la columna fecha_referencia tiene tipo string") for problem in problems)
    assert any(problem.startswith("la columna es_control tiene tipo int64; se esperaba bool") for problem in problems)


def test_default_pandas_text_dtype_is_rejected_until_cast_to_schema():
    frame = valid_frame()
    frame["sexo"] = pd.Series(["total", "total", "total", "mujeres"])

    with pytest.raises(ValueError, match="la columna sexo tiene tipo"):
        DemografiaSchema().validate(frame)


def test_values_outside_closed_domains_are_rejected():
    frame = valid_frame()
    frame["sexo"] = pd.Series(["Total", "ambos sexos", "total", "mujeres"], dtype="string")
    frame["tipo_edad"] = pd.Series(["simple", "intervalo", "total", "tramo_abierto"], dtype="string")
    frame["estado_dato"] = pd.Series(["observado", "observado", "definitivo", "proyectado"], dtype="string")
    frame["escenario"] = pd.Series(["observado", "observado", "observado", "Central"], dtype="string")

    problems = DemografiaSchema().problems(frame)

    assert [problem.split(" tiene ")[0] for problem in problems] == [
        "la columna sexo",
        "la columna tipo_edad",
        "la columna estado_dato",
        "la columna escenario",
    ]
    assert "Total, ambos sexos" in problems[0]
    assert "Central" in problems[3]


def test_nulls_in_required_columns_are_rejected():
    frame = valid_frame()
    frame.loc[0, "codigo_serie"] = pd.NA
    frame.loc[1, "sexo"] = pd.NA

    problems = DemografiaSchema().problems(frame)

    assert "la columna codigo_serie tiene 1 valores nulos y no admite nulos" in problems
    assert "la columna sexo tiene 1 valores nulos y no admite nulos" in problems


def test_every_problem_is_reported_together():
    frame = valid_frame().drop(columns=["unidad"])
    frame["sexo"] = pd.Series(["x", "total", "total", "mujeres"], dtype="string")

    with pytest.raises(ValueError, match="faltan columnas: unidad; la columna sexo tiene valores fuera de dominio: x"):
        DemografiaSchema().validate(frame)
