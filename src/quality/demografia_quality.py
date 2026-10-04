from datetime import date

import pandas as pd

from src.quality.quality_evaluation import QualityEvaluation
from src.transform.age_partition import GROUP_KEYS
from src.transform.demografia_schema import DemografiaSchema

BUSINESS_KEY = ["metrica", "territorio", "fecha_referencia", "sexo", "tipo_edad", "edad_min", "edad_max", "escenario"]
SAMPLE_SIZE = 5
NON_NEGATIVE_METRICS = ("poblacion", "nacimientos", "defunciones")
STRUCTURAL_NULL_COLUMNS = ("edad_max",)
RULES = (
    ("valores_no_nulos", "SLV-005: ninguna fila sin valor"),
    ("fraccion_nulos", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage; edad_max es nula por diseño y la controla edad_max_estructural"),
    ("no_negativos", "QLT-002: población, nacimientos y defunciones no negativos"),
    ("edad_max_estructural", "QLT-002: edad_max nula solo en tramos abiertos y totales"),
    ("clave_unica", "SLV-005: clave de negocio sin duplicados"),
    ("sin_mezcla_observado_proyectado", "SLV-005: ninguna clave mezcla observado y proyectado"),
    ("totales_por_edad", "SLV-005: detalle igual a 'Todas las edades' dentro de la tolerancia aprobada"),
    ("tramo_homologado", "SLV-003: tramo homologado igual a la suma de sus componentes"),
)


class DemografiaQuality:
    def __init__(self, validation_config, max_null_fraction):
        self.schema = DemografiaSchema()
        self.max_null_fraction = max_null_fraction
        self.rules = [
            {
                "table_id": rule["table_id"],
                "before": date.fromisoformat(rule["before"]),
                "max_abs_difference": rule["max_abs_difference"],
            }
            for rule in validation_config["age_total_tolerances"]
        ]
        self.default_tolerance = validation_config["default_max_abs_difference"]
        self.epsilon = validation_config["float_epsilon"]

    def validate(self, frame, homologation):
        evaluation = QualityEvaluation()
        self.evaluate(frame, homologation, evaluation)
        if not evaluation.passed():
            raise ValueError(evaluation.rejection("Plata"))
        return evaluation

    def problems(self, frame, homologation):
        evaluation = QualityEvaluation()
        self.evaluate(frame, homologation, evaluation)
        return evaluation.problems()

    def evaluate(self, frame, homologation, evaluation):
        evaluation.metrics["filas"] = len(frame)
        if not evaluation.check("esquema", "QLT-001: columnas, tipos, nulos obligatorios y dominios de DemografiaSchema", self.schema.problems(frame)):
            for name, description in RULES:
                evaluation.skip(name, description, "el esquema no se cumple")
            return evaluation
        evaluation.metrics["filas_por_metrica"] = {str(key): int(value) for key, value in frame.groupby("metrica").size().items()}
        problems = {
            "valores_no_nulos": self._null_values(frame),
            "fraccion_nulos": evaluation.null_fractions(frame, self.max_null_fraction, STRUCTURAL_NULL_COLUMNS),
            "no_negativos": self._negative_values(frame),
            "edad_max_estructural": self._structural_age_nulls(frame),
            "clave_unica": self._duplicated_keys(frame),
            "sin_mezcla_observado_proyectado": self._mixed_states(frame),
            "totales_por_edad": self._age_totals(frame),
            "tramo_homologado": self._homologation(homologation),
        }
        for name, description in RULES:
            evaluation.check(name, description, problems[name])
        return evaluation

    def tolerance(self, table_ids, fechas):
        tolerance = pd.Series(float(self.default_tolerance), index=table_ids.index)
        for rule in self.rules:
            applies = table_ids.eq(rule["table_id"]) & fechas.lt(rule["before"])
            tolerance = tolerance.mask(applies.astype(bool), float(rule["max_abs_difference"]))
        return tolerance + self.epsilon

    def _null_values(self, frame):
        missing = int(frame["valor"].isna().sum())
        return [f"{missing} filas sin valor"] if missing else []

    def _negative_values(self, frame):
        negative = frame["metrica"].isin(NON_NEGATIVE_METRICS) & frame["valor"].lt(0)
        if not negative.any():
            return []
        sample = frame.loc[negative, ["tabla_id", "metrica", "anyo", "valor"]].head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(negative.sum())} valores negativos de población, nacimientos o defunciones; por ejemplo {sample}"]

    def _structural_age_nulls(self, frame):
        inconsistent = frame["edad_max"].isna().ne(frame["tipo_edad"].ne("simple"))
        if not inconsistent.any():
            return []
        sample = frame.loc[inconsistent, ["tabla_id", "tipo_edad", "edad_min", "edad_max"]].head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(inconsistent.sum())} filas con edad_max incoherente con tipo_edad; por ejemplo {sample}"]

    def _duplicated_keys(self, frame):
        duplicated = frame.duplicated(BUSINESS_KEY, keep=False)
        if not duplicated.any():
            return []
        sample = frame.loc[duplicated, BUSINESS_KEY + ["tabla_id", "valor"]].head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(duplicated.sum())} filas repiten la clave de negocio {BUSINESS_KEY}; por ejemplo {sample}"]

    def _mixed_states(self, frame):
        key = [column for column in BUSINESS_KEY if column != "escenario"]
        states = frame.groupby(key, dropna=False)["estado_dato"].nunique()
        mixed = states[states.gt(1)]
        if mixed.empty:
            return []
        return [f"{len(mixed)} claves mezclan datos observados y proyectados; por ejemplo {mixed.head(SAMPLE_SIZE).index.tolist()}"]

    def _age_totals(self, frame):
        age_tables = frame.loc[frame["tipo_edad"].ne("total"), "tabla_id"].unique()
        aged = frame[frame["tabla_id"].isin(age_tables)]
        detail = aged[~aged["es_control"]].groupby(GROUP_KEYS, dropna=False)["valor"].sum().rename("detalle")
        totals = aged[aged["es_control"] & aged["tipo_edad"].eq("total")].groupby(GROUP_KEYS, dropna=False)["valor"].sum().rename("total")
        comparison = pd.concat([detail, totals], axis=1).reset_index()
        problems = []
        unmatched = comparison["detalle"].isna() | comparison["total"].isna()
        if unmatched.any():
            problems.append(
                f"{int(unmatched.sum())} grupos periodo × sexo sin pareja detalle/total; "
                f"por ejemplo {comparison.loc[unmatched, GROUP_KEYS].head(SAMPLE_SIZE).to_dict('records')}"
            )
        difference = (comparison["detalle"] - comparison["total"]).abs()
        exceeded = ~unmatched & difference.gt(self.tolerance(comparison["tabla_id"], comparison["fecha_referencia"]))
        if exceeded.any():
            sample = comparison.loc[exceeded].assign(diferencia=difference[exceeded]).head(SAMPLE_SIZE).to_dict("records")
            problems.append(f"{int(exceeded.sum())} grupos no cuadran detalle con 'Todas las edades'; por ejemplo {sample}")
        return problems

    def _homologation(self, homologation):
        if homologation.empty:
            return []
        difference = (homologation["published"] - homologation["components"]).abs()
        exceeded = difference.gt(self.tolerance(homologation["tabla_id"], homologation["fecha_referencia"]))
        if not exceeded.any():
            return []
        sample = homologation.loc[exceeded].head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(exceeded.sum())} grupos con tramo homologado distinto de la suma de sus componentes; por ejemplo {sample}"]
