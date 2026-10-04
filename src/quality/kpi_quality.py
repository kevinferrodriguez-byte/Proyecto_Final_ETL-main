from src.indicators.demografia_kpis import AGE_GROUPS, KEYS
from src.indicators.kpi_schema import KpiSchema

KPI_KEY = ["anyo", "territorio", "escenario", "indicador"]
SAMPLE_SIZE = 5
RATIO_INDICATORS = ("indice_envejecimiento", "tasa_dependencia", "tasa_dependencia_mayores")
RULES = (
    ("valores_no_nulos", "GLD-006: todos los KPIs tienen valor"),
    ("fraccion_nulos", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage"),
    ("denominadores_positivos", "GLD-006 y QLT-002: población menor de 16 y de 16 a 64 años mayor que cero"),
    ("edades_asignadas", "GLD-002: toda fila de detalle pertenece a un grupo de edad por rango numérico"),
    ("grupos_suman_total", "GLD-002: los tres grupos de edad suman la población total de detalle"),
    ("poblacion_no_negativa", "QLT-002: población por grupo de edad no negativa"),
    ("eventos_completos", "GLD-005: cada año con nacimientos tiene defunciones y viceversa, sin valores negativos"),
    ("saldo_solo_observado", "GLD-005: el saldo vegetativo solo se calcula con datos observados"),
    ("clave_unica", "GLD-001: una fila por año, territorio, escenario e indicador"),
    ("sin_mezcla_observado_proyectado", "GLD-006: observado y proyectado nunca comparten clave"),
)


class KpiQuality:
    def __init__(self, gold_config, max_null_fraction):
        self.schema = KpiSchema()
        self.epsilon = gold_config["float_epsilon"]
        self.max_null_fraction = max_null_fraction

    def evaluate(self, computed, evaluation):
        frame = computed["frame"]
        evaluation.metrics["filas"] = len(frame)
        if not evaluation.check("esquema", "QLT-001: columnas, tipos, nulos obligatorios y dominios de KpiSchema", self.schema.problems(frame)):
            for name, description in RULES:
                evaluation.skip(name, description, "el esquema no se cumple")
            return evaluation
        evaluation.metrics["filas_por_indicador_y_escenario_kr"] = {
            f"{indicator}|{scenario}": int(count) for (indicator, scenario), count in frame.groupby(["indicador", "escenario_kr"]).size().items()
        }
        groups = computed["age_groups"]
        vital = computed["vital"]
        problems = {
            "valores_no_nulos": self._null_values(frame),
            "fraccion_nulos": evaluation.null_fractions(frame, self.max_null_fraction, ()),
            "denominadores_positivos": self._denominators(groups),
            "edades_asignadas": self._unassigned(groups),
            "grupos_suman_total": self._group_totals(groups),
            "poblacion_no_negativa": self._negative_groups(groups),
            "eventos_completos": self._vital(vital),
            "saldo_solo_observado": self._balance_state(frame),
            "clave_unica": self._duplicated_keys(frame),
            "sin_mezcla_observado_proyectado": self._mixed_states(frame),
        }
        for name, description in RULES:
            evaluation.check(name, description, problems[name])
        return evaluation

    def _null_values(self, frame):
        missing = frame["valor"].isna()
        if not missing.any():
            return []
        sample = frame.loc[missing, KPI_KEY].head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(missing.sum())} KPIs sin valor; por ejemplo {sample}"]

    def _denominators(self, groups):
        invalid = groups["menores_16"].le(0) | groups["activos_16_64"].le(0)
        if not invalid.any():
            return []
        sample = groups.loc[invalid, KEYS + ["menores_16", "activos_16_64"]].head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(invalid.sum())} grupos con denominador no positivo (división por cero rechazada); por ejemplo {sample}"]

    def _unassigned(self, groups):
        unassigned = groups["filas_sin_grupo"].gt(0)
        if not unassigned.any():
            return []
        sample = groups.loc[unassigned, KEYS + ["filas_sin_grupo"]].head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(groups['filas_sin_grupo'].sum())} filas de edad inesperada sin grupo; por ejemplo {sample}"]

    def _group_totals(self, groups):
        difference = (groups[AGE_GROUPS].sum(axis=1) - groups["total_detalle"]).abs()
        exceeded = difference.gt(self.epsilon)
        if not exceeded.any():
            return []
        sample = groups.loc[exceeded, KEYS].assign(diferencia=difference[exceeded]).head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(exceeded.sum())} grupos cuya suma por edades no coincide con la población total; por ejemplo {sample}"]

    def _negative_groups(self, groups):
        negative = groups[AGE_GROUPS].lt(0).any(axis=1)
        if not negative.any():
            return []
        return [f"{int(negative.sum())} grupos con población negativa; por ejemplo {groups.loc[negative, KEYS].head(SAMPLE_SIZE).to_dict('records')}"]

    def _vital(self, vital):
        incomplete = vital[["nacimientos", "defunciones"]].isna().any(axis=1)
        negative = vital[["nacimientos", "defunciones"]].lt(0).any(axis=1)
        problems = []
        if incomplete.any():
            problems.append(f"{int(incomplete.sum())} años sin nacimientos o sin defunciones; por ejemplo {vital.loc[incomplete, KEYS].head(SAMPLE_SIZE).to_dict('records')}")
        if negative.any():
            problems.append(f"{int(negative.sum())} años con nacimientos o defunciones negativos")
        return problems

    def _balance_state(self, frame):
        projected = frame["indicador"].eq("saldo_vegetativo") & frame["estado_dato"].ne("observado")
        return [f"{int(projected.sum())} saldos vegetativos no observados"] if projected.any() else []

    def _duplicated_keys(self, frame):
        duplicated = frame.duplicated(KPI_KEY, keep=False)
        if not duplicated.any():
            return []
        return [f"{int(duplicated.sum())} filas repiten la clave {KPI_KEY}; por ejemplo {frame.loc[duplicated, KPI_KEY].head(SAMPLE_SIZE).to_dict('records')}"]

    def _mixed_states(self, frame):
        states = frame.groupby(["anyo", "territorio", "indicador"])["estado_dato"].nunique()
        mixed = states[states.gt(1)]
        if mixed.empty:
            return []
        return [f"{len(mixed)} claves mezclan observado y proyectado; por ejemplo {mixed.head(SAMPLE_SIZE).index.tolist()}"]
