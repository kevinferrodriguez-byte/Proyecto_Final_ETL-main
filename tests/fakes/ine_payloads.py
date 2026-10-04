from pathlib import Path

import pandas as pd
import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
TIMEZONE = "Europe/Madrid"
SEX = {"total": (18, "Total"), "ambos": (18, "Ambos sexos"), "hombres": (18, "Hombres"), "mujeres": (18, "Mujeres")}
SPAIN = (349, "Total Nacional")
POPULATION = (260, "Población")


def load_config():
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def fecha_ms(year, month, day):
    return int(pd.Timestamp(year=year, month=month, day=day, tz=TIMEZONE).value // 1_000_000)


def point(year, valor, month=1, day=1):
    return {"Fecha": fecha_ms(year, month, day), "FK_TipoDato": 1, "FK_Periodo": 19, "Anyo": year, "Valor": valor, "Secreto": False}


def series(code, metadata, points, unit=3):
    return {
        "COD": code,
        "Nombre": "",
        "FK_Unidad": unit,
        "FK_Escala": 1,
        "MetaData": [
            {"Id": position, "FK_Variable": variable, "Nombre": label, "Codigo": ""}
            for position, (variable, label) in enumerate(metadata)
        ],
        "Data": points,
    }


def age(label):
    if label == "Todas las edades":
        return (356, label)
    if "y más" in label:
        return (357, label)
    return (355, label)


def population_series(code, sex, age_label, points, extra=None):
    metadata = [SPAIN, SEX[sex], POPULATION, age(age_label), (3, "Número")] + (extra or [])
    return series(code, metadata, points)


def projection_series(code, sex, age_label, points, scenario=None):
    metadata = [SPAIN, SEX[sex], POPULATION, age(age_label), (3, "Proyección a largo plazo")]
    if scenario is not None:
        metadata.append((876, scenario))
    return series(code, metadata, points)


def births_deaths(points_by_concept):
    units = {"Nacimiento": 120, "Defunción": 122}
    codes = {"Nacimiento": "MNP17544", "Defunción": "MNP17542"}
    return [
        series(codes[concept], [SPAIN, (260, concept), (3, "Dato base")], points, units[concept])
        for concept, points in points_by_concept.items()
    ]


def migration_24309(points):
    return [series("EM24309", [(141, "Total"), (260, "Saldo con el extranjero"), SPAIN, (431, "Total")], points, 155)]


def migration_69758(points):
    return [series("EM69758", [(141, "Total"), SEX["ambos"], (876, "Saldo exterior"), (3, "Dato base")], points, 420)]


def fertility_1407(points):
    metadata = [SPAIN, (259, "Fecundidad"), (260, "Indicador coyuntural de fecundidad"), (310, "Anual"), (3, "Dato base"), (141, "Ambas nacionalidades"), (452, "Todos")]
    return [series("IDB72160", metadata, points, 110)]


def life_expectancy(table_id, points_by_sex):
    age_label = {"1414": "0 años", "1415": "65 años"}[table_id]
    return [
        series(f"IDB{table_id}{sex}", [SPAIN, (259, "Mortalidad"), (260, "Esperanza de vida"), SEX[sex], (355, age_label), (310, "Anual"), (3, "Dato base")], points, 108)
        for sex, points in points_by_sex.items()
    ]
