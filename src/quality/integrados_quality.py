import pandas as pd

from src.indicators.integrados_schema import INTEGRATED_INDICATORS, KpiIntegradoSchema

KEY = ["anyo", "territorio", "indicador"]
SAMPLE_SIZE = 5
RULES = (
    ("valores_no_nulos", "INT-QLT: todo KPI integrado tiene valor, numerador y denominador"),
    ("fraccion_nulos", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage (valor_publicado solo existe para gasto/PIB)"),
    ("denominadores_positivos", "INT-QLT: denominadores (PIB, población 16-64) mayores que cero"),
    ("coherencia_calculo", "INT-QLT: valor = numerador / denominador × 100"),
    ("rangos_validos", "INT-QLT: cada KPI dentro del rango del catálogo modelo.indicators"),
    ("clave_unica", "INT-QLT: una fila por año, territorio e indicador"),
    ("fechas_alineadas", "INT-QLT: en la tasa de afiliación, población a 1/1 del año siguiente a la afiliación de 31/12 (1 día)"),
    ("completitud_temporal", "QLT-003: años presentes / cobertura esperada del catálogo >= quality.min_temporal_completeness"),
)
PUBLISHED_RULE = ("consistencia_publicado", "INT-QLT: gasto/PIB calculado frente al porcentaje publicado por Eurostat (advierte si supera max_diferencia_publicado_pp)")
STRUCTURAL_NULL_COLUMNS = ("valor_publicado", "diferencia_publicado")


class IntegradosQuality:
    def __init__(self, config):
        integrated = config["indicadores"]["integrados"]
        self.epsilon = integrated["float_epsilon"]
        self.max_published_difference = integrated["max_diferencia_publicado_pp"]
        self.catalog = config["modelo"]["indicators"]
        self.max_null_fraction = config["quality"]["max_null_percentage"]
        self.min_completeness = config["quality"]["min_temporal_completeness"]
        self.schema = KpiIntegradoSchema()

    def evaluate(self, frame, evaluation):
        evaluation.metrics["filas"] = len(frame)
        if not evaluation.check("esquema", "QLT-001: columnas, tipos, nulos obligatorios y dominios de KpiIntegradoSchema", self.schema.problems(frame)):
            for name, description in (*RULES, PUBLISHED_RULE):
                evaluation.skip(name, description, "el esquema no se cumple")
            return evaluation
        evaluation.metrics["filas_por_indicador"] = {str(key): int(value) for key, value in frame.groupby("indicador").size().items()}
        problems = {
            "valores_no_nulos": self._flagged(frame, frame[["valor", "numerador", "denominador"]].isna().any(axis=1), "filas sin valor, numerador o denominador"),
            "fraccion_nulos": self._null_fraction(evaluation, frame),
            "denominadores_positivos": self._flagged(frame, frame["denominador"].le(0), "denominadores no positivos"),
            "coherencia_calculo": self._coherence(frame),
            "rangos_validos": self._ranges(frame),
            "clave_unica": self._flagged(frame, frame.duplicated(KEY, keep=False), f"filas repiten la clave {KEY}"),
            "fechas_alineadas": self._dates(frame),
            "completitud_temporal": self._coverage(evaluation, frame),
        }
        for name, description in RULES:
            evaluation.check(name, description, problems[name])
        evaluation.warn(*PUBLISHED_RULE, self._published(evaluation, frame))
        return evaluation

    def _flagged(self, frame, mask, label):
        mask = mask.fillna(False).astype(bool)
        if not mask.any():
            return []
        return [f"{int(mask.sum())} {label}; por ejemplo {frame.loc[mask, KEY + ['valor']].head(SAMPLE_SIZE).to_dict('records')}"]

    def _null_fraction(self, evaluation, frame):
        return evaluation.null_fractions(frame, self.max_null_fraction, STRUCTURAL_NULL_COLUMNS)

    def _coherence(self, frame):
        expected = frame["numerador"] / frame["denominador"].where(frame["denominador"].gt(0)) * 100
        incoherent = (frame["valor"] - expected).abs().gt(self.epsilon * expected.abs().clip(lower=1))
        return self._flagged(frame, incoherent, "valores distintos de numerador / denominador × 100")

    def _ranges(self, frame):
        problems = []
        for indicator in INTEGRATED_INDICATORS:
            bounds = self.catalog[indicator]["rango"]
            outside = frame["indicador"].eq(indicator) & ~frame["valor"].between(bounds["min"], bounds["max"])
            problems.extend(self._flagged(frame, outside, f"valores de {indicator} fuera de [{bounds['min']}, {bounds['max']}]"))
        return problems

    def _dates(self, frame):
        affiliation = frame["indicador"].eq("tasa_afiliacion_16_64")
        gap = pd.to_datetime(frame["fecha_referencia_denominador"].astype(str)) - pd.to_datetime(frame["fecha_referencia_numerador"].astype(str))
        misaligned = affiliation & gap.ne(pd.Timedelta(days=1))
        return self._flagged(frame, misaligned, "tasas de afiliación cuyo denominador no es el 1 de enero siguiente")

    def _coverage(self, evaluation, frame):
        coverage = []
        problems = []
        for indicator in INTEGRATED_INDICATORS:
            window = self.catalog[indicator]["cobertura"]
            expected = set(range(window["desde"], window["hasta"] + 1))
            years = set(frame.loc[frame["indicador"].eq(indicator), "anyo"].astype(int))
            completeness = len(expected & years) / len(expected)
            coverage.append({"indicador": indicator, "esperados": len(expected), "presentes": len(expected & years), "completitud": round(completeness, 6), "faltantes": sorted(expected - years)[:SAMPLE_SIZE]})
            if completeness < self.min_completeness:
                problems.append(f"{indicator}: completitud {completeness:.2%} por debajo de {self.min_completeness:.0%}; faltan {sorted(expected - years)[:SAMPLE_SIZE]}")
        evaluation.metrics["completitud_temporal"] = coverage
        return problems

    def _published(self, evaluation, frame):
        compared = frame[frame["diferencia_publicado"].notna()]
        evaluation.metrics["diferencia_publicado_max_pp"] = round(float(compared["diferencia_publicado"].abs().max()), 6) if len(compared) else None
        exceeded = compared["diferencia_publicado"].abs().gt(self.max_published_difference)
        return [
            f"{int(row.anyo)}: calculado {row.valor:.4f} frente a publicado {row.valor_publicado:.2f} (diferencia {row.diferencia_publicado:+.4f} pp)"
            for row in compared[exceeded].itertuples()
        ]
