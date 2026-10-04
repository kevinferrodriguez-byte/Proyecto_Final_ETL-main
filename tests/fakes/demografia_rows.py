from datetime import date

import pandas as pd

from src.transform.demografia_schema import DemografiaSchema


DEFAULT_ROW = {
    "fuente": "Instituto Nacional de Estadística",
    "tabla_id": "56934",
    "consulta": "detalle",
    "run_id": "ine_20260926T000000.000000Z",
    "codigo_serie": "ECP",
    "fecha_referencia": date(2020, 1, 1),
    "anyo": 2020,
    "territorio": "ES",
    "sexo": "total",
    "edad_min": 0,
    "edad_max": 0,
    "edad_etiqueta_original": "0 años",
    "tipo_edad": "simple",
    "metrica": "poblacion",
    "valor": 1.0,
    "unidad": "personas",
    "estado_dato": "observado",
    "escenario": "observado",
    "es_control": False,
}


def frame_from(rows):
    records = []
    for row in rows:
        record = dict(DEFAULT_ROW)
        record.update(row)
        records.append(record)
    schema = DemografiaSchema()
    return pd.DataFrame(
        {name: pd.Series([record[name] for record in records], dtype=dtype) for name, dtype in schema.dtypes.items()}
    )


def simple_age(age, valor, row):
    record = {"tipo_edad": "simple", "edad_min": age, "edad_max": age, "edad_etiqueta_original": f"{age} años", "valor": valor}
    record.update(row)
    return record


def open_interval(age, valor, row):
    record = {"tipo_edad": "tramo_abierto", "edad_min": age, "edad_max": None, "edad_etiqueta_original": f"{age} y más años", "valor": valor}
    record.update(row)
    return record


def all_ages(valor, row):
    record = {
        "tipo_edad": "total",
        "edad_min": 0,
        "edad_max": None,
        "edad_etiqueta_original": "Todas las edades",
        "valor": valor,
        "consulta": "total_edad",
        "es_control": True,
    }
    record.update(row)
    return record


def valid_frame():
    rows = {
        "fuente": ["Instituto Nacional de Estadística"] * 4,
        "tabla_id": ["56934", "56934", "56934", "36652"],
        "consulta": ["detalle", "detalle", "total_edad", "detalle"],
        "run_id": ["ine_20260926T030953.541890Z"] * 4,
        "codigo_serie": ["ECP1", "ECP2", "ECP320", "PPR1"],
        "fecha_referencia": [date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1), date(2030, 1, 1)],
        "anyo": [2025, 2025, 2025, 2030],
        "territorio": ["ES"] * 4,
        "sexo": ["total", "total", "total", "mujeres"],
        "edad_min": [0, 105, 0, 100],
        "edad_max": [0, None, None, None],
        "edad_etiqueta_original": ["0 años", "105 y más años", "Todas las edades", "100 y más años"],
        "tipo_edad": ["simple", "tramo_abierto", "total", "tramo_abierto"],
        "metrica": ["poblacion"] * 4,
        "valor": [331015.0, 810.0, 49128297.0, 9876.0],
        "unidad": ["personas"] * 4,
        "estado_dato": ["observado", "observado", "observado", "proyectado"],
        "escenario": ["observado", "observado", "observado", "fecundidad_alta"],
        "es_control": [False, False, True, False],
    }
    schema = DemografiaSchema()
    return pd.DataFrame({name: pd.Series(values, dtype=schema.dtypes[name]) for name, values in rows.items()})
