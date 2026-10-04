import pandas as pd

from src.quality.quality_evaluation import QualityEvaluation
from src.transform.seguridad_social.seguridad_social_schema import IMPORTE_CLASSES, PENSION_CLASSES, AfiliadosSchema, ImporteSchema, PensionesSchema

AFILIADOS_KEY = ["territorio", "anyo", "mes"]
PENSIONES_KEY = ["territorio", "tipo_corte", "anyo", "mes"]
PENSION_COUNTS = list(PENSION_CLASSES) + ["total_pensiones"]
IMPORTE_AMOUNTS = list(IMPORTE_CLASSES) + ["importe_total"]
SAMPLE_SIZE = 5
AFILIADOS_RULES = (
    ("valores_no_nulos", "SS-QLT: todo mes tiene total_afiliados"),
    ("fraccion_nulos", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage"),
    ("valores_positivos", "SS-QLT: total_afiliados mayor que cero"),
    ("mes_valido", "SS-QLT: mes entre 1 y 12"),
    ("fechas_coherentes", "SS-QLT: anyo y mes coinciden con fecha_referencia (último día del mes) y ninguna fecha es futura"),
    ("clave_unica", "SS-QLT: una fila por territorio, año y mes"),
    ("completitud_temporal", "SS-QLT: meses presentes dentro de la cobertura esperada >= quality.min_temporal_completeness"),
)
PENSIONES_RULES = (
    ("valores_no_nulos", "SS-QLT: toda fila tiene el total y las cinco clases de pensión"),
    ("fraccion_nulos", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage"),
    ("total_positivo", "SS-QLT: total_pensiones mayor que cero"),
    ("clases_no_negativas", "SS-QLT: pensiones por clase no negativas"),
    ("mes_valido", "SS-QLT: mes entre 1 y 12"),
    ("corte_anual_en_mes_de_referencia", "SS-QLT: las filas anuales usan el mes de la nota de la fuente (annual_reference.month)"),
    ("fechas_coherentes", "SS-QLT: anyo y mes coinciden con fecha_referencia (día 1 del mes) y ninguna fecha es futura"),
    ("clave_unica", "SS-QLT: una fila por territorio, tipo de corte, año y mes"),
    ("clases_no_superan_total", "SS-QLT: ninguna clase de pensión supera total_pensiones"),
    ("clases_suman_total", "SS-QLT: las cinco clases de pensión suman total_pensiones"),
    ("anual_igual_a_mensual_de_referencia", "SS-QLT: el dato anual coincide con el mensual del mes de referencia cuando ambos existen"),
    ("completitud_temporal_anual", "SS-QLT: años presentes dentro de la cobertura anual esperada >= quality.min_temporal_completeness"),
    ("completitud_temporal_mensual", "SS-QLT: meses presentes dentro de la cobertura mensual esperada >= quality.min_temporal_completeness"),
)
IMPORTE_RULES = (
    ("valores_no_nulos", "SS-QLT: toda fila tiene el importe total y el de las cinco clases"),
    ("fraccion_nulos", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage"),
    ("total_positivo", "SS-QLT: importe_total mayor que cero"),
    ("clases_no_negativas", "SS-QLT: importe por clase no negativo"),
    ("fechas_coherentes", "SS-QLT: anyo y mes coinciden con fecha_referencia (día 1 del mes) y ninguna fecha es futura"),
    ("clave_unica", "SS-QLT: una fila por territorio, tipo de corte, año y mes"),
    ("clases_suman_total", "SS-QLT: las cinco clases suman importe_total dentro de importe.sum_tolerance (miles de euros)"),
    ("periodos_iguales_a_numero", "SS-QLT: el importe cubre exactamente los mismos periodos que el número de pensiones (consistencia entre hojas)"),
    ("completitud_temporal_anual", "SS-QLT: años presentes dentro de la cobertura anual esperada >= quality.min_temporal_completeness"),
)


class SeguridadSocialQuality:
    def __init__(self, silver_config, quality_config):
        self.afiliados_periods = silver_config["afiliados"]["periods"]
        self.pensiones_periods = silver_config["pensiones"]["periods"]
        self.annual_month = silver_config["pensiones"]["annual_reference"]["month"]
        self.importe_config = silver_config.get("importe")
        self.max_null_fraction = quality_config["max_null_percentage"]
        self.min_completeness = quality_config["min_temporal_completeness"]

    def evaluate(self, afiliados, pensiones, evaluation, today, importe=None):
        self._merge(evaluation, "afiliados", self.evaluate_afiliados(afiliados, today))
        self._merge(evaluation, "pensiones", self.evaluate_pensiones(pensiones, today))
        if importe is not None:
            self._merge(evaluation, "importe", self.evaluate_importe(importe, pensiones, today))
        return evaluation

    def evaluate_importe(self, frame, pensiones, today):
        evaluation = QualityEvaluation()
        evaluation.metrics["filas"] = len(frame)
        if not evaluation.check("esquema", "QLT-001: columnas, tipos, nulos obligatorios y dominios de ImporteSchema", ImporteSchema().problems(frame)):
            self._skip(evaluation, IMPORTE_RULES)
            return evaluation
        annual = frame[frame["tipo_corte"].eq("anual")]
        periods = self.importe_config["periods"]
        expected_years = self._years(periods["annual_expected_start"], periods["annual_expected_end"], annual)
        problems = {
            "valores_no_nulos": self._nulls(frame, IMPORTE_AMOUNTS, PENSIONES_KEY),
            "fraccion_nulos": evaluation.null_fractions(frame, self.max_null_fraction, ()),
            "total_positivo": self._below(frame, ["importe_total"], 1e-9, PENSIONES_KEY, "importe_total no positivos"),
            "clases_no_negativas": self._below(frame, list(IMPORTE_CLASSES), 0, PENSIONES_KEY, "filas con algún importe de clase negativo"),
            "fechas_coherentes": self._dates(frame, today, last_day=False),
            "clave_unica": self._duplicated(frame, PENSIONES_KEY),
            "clases_suman_total": self._amounts_sum(frame),
            "periodos_iguales_a_numero": self._same_periods(frame, pensiones),
            "completitud_temporal_anual": self._coverage(evaluation, "completitud_temporal_anual", set(annual["anyo"].astype(int)), expected_years),
        }
        self._check(evaluation, IMPORTE_RULES, problems)
        return evaluation

    def _amounts_sum(self, frame):
        difference = (frame[list(IMPORTE_CLASSES)].sum(axis=1, min_count=len(IMPORTE_CLASSES)) - frame["importe_total"]).abs()
        mismatched = difference.gt(self.importe_config["sum_tolerance"]).fillna(False)
        if not mismatched.any():
            return []
        sample = frame.loc[mismatched, PENSIONES_KEY].assign(diferencia=difference[mismatched]).head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(mismatched.sum())} filas cuyos importes por clase no suman importe_total; por ejemplo {sample}"]

    def _same_periods(self, frame, pensiones):
        amounts = set(map(tuple, frame[PENSIONES_KEY].astype(str).to_numpy()))
        counts = set(map(tuple, pensiones[PENSIONES_KEY].astype(str).to_numpy()))
        if amounts == counts:
            return []
        return [f"periodos solo en importe: {sorted(amounts - counts)[:SAMPLE_SIZE]}; solo en número: {sorted(counts - amounts)[:SAMPLE_SIZE]}"]

    def evaluate_afiliados(self, frame, today):
        evaluation = QualityEvaluation()
        evaluation.metrics["filas"] = len(frame)
        if not evaluation.check("esquema", "QLT-001: columnas, tipos, nulos obligatorios y dominios de AfiliadosSchema", AfiliadosSchema().problems(frame)):
            self._skip(evaluation, AFILIADOS_RULES)
            return evaluation
        expected = self._months(self.afiliados_periods["expected_start"], self.afiliados_periods["expected_end"], frame)
        problems = {
            "valores_no_nulos": self._nulls(frame, ["total_afiliados"], AFILIADOS_KEY),
            "fraccion_nulos": evaluation.null_fractions(frame, self.max_null_fraction, ()),
            "valores_positivos": self._below(frame, ["total_afiliados"], 1, AFILIADOS_KEY, "total_afiliados no positivos"),
            "mes_valido": self._invalid_months(frame),
            "fechas_coherentes": self._dates(frame, today, last_day=True),
            "clave_unica": self._duplicated(frame, AFILIADOS_KEY),
            "completitud_temporal": self._coverage(evaluation, "completitud_temporal", self._observed_months(frame), expected),
        }
        self._check(evaluation, AFILIADOS_RULES, problems)
        return evaluation

    def evaluate_pensiones(self, frame, today):
        evaluation = QualityEvaluation()
        evaluation.metrics["filas"] = len(frame)
        if not evaluation.check("esquema", "QLT-001: columnas, tipos, nulos obligatorios y dominios de PensionesSchema", PensionesSchema().problems(frame)):
            self._skip(evaluation, PENSIONES_RULES)
            return evaluation
        evaluation.metrics["filas_por_tipo_corte"] = {str(key): int(value) for key, value in frame.groupby("tipo_corte").size().items()}
        annual = frame[frame["tipo_corte"].eq("anual")]
        monthly = frame[frame["tipo_corte"].eq("mensual")]
        periods = self.pensiones_periods
        expected_years = self._years(periods["annual_expected_start"], periods["annual_expected_end"], annual)
        expected_months = self._months(periods["monthly_expected_start"], periods["monthly_expected_end"], monthly)
        problems = {
            "valores_no_nulos": self._nulls(frame, PENSION_COUNTS, PENSIONES_KEY),
            "fraccion_nulos": evaluation.null_fractions(frame, self.max_null_fraction, ()),
            "total_positivo": self._below(frame, ["total_pensiones"], 1, PENSIONES_KEY, "total_pensiones no positivos"),
            "clases_no_negativas": self._below(frame, list(PENSION_CLASSES), 0, PENSIONES_KEY, "filas con alguna clase de pensión negativa"),
            "mes_valido": self._invalid_months(frame),
            "corte_anual_en_mes_de_referencia": self._annual_month(annual),
            "fechas_coherentes": self._dates(frame, today, last_day=False),
            "clave_unica": self._duplicated(frame, PENSIONES_KEY),
            "clases_no_superan_total": self._classes_above_total(frame),
            "clases_suman_total": self._classes_sum(frame),
            "anual_igual_a_mensual_de_referencia": self._annual_matches_monthly(evaluation, annual, monthly),
            "completitud_temporal_anual": self._coverage(evaluation, "completitud_temporal_anual", set(annual["anyo"].astype(int)), expected_years),
            "completitud_temporal_mensual": self._coverage(evaluation, "completitud_temporal_mensual", self._observed_months(monthly), expected_months),
        }
        self._check(evaluation, PENSIONES_RULES, problems)
        return evaluation

    def _merge(self, evaluation, dataset, partial):
        evaluation.rules.extend({**rule, "regla": f"{dataset}.{rule['regla']}"} for rule in partial.rules)
        evaluation.metrics[dataset] = partial.metrics

    def _skip(self, evaluation, rules):
        for name, description in rules:
            evaluation.skip(name, description, "el esquema no se cumple")

    def _check(self, evaluation, rules, problems):
        for name, description in rules:
            evaluation.check(name, description, problems[name])

    def _nulls(self, frame, columns, key):
        missing = frame[columns].isna().any(axis=1)
        if not missing.any():
            return []
        return [f"{int(missing.sum())} filas sin valor en {', '.join(columns)}; por ejemplo {self._sample(frame, missing, key)}"]

    def _below(self, frame, columns, minimum, key, label):
        invalid = frame[columns].lt(minimum).fillna(False).any(axis=1)
        if not invalid.any():
            return []
        return [f"{int(invalid.sum())} {label}; por ejemplo {self._sample(frame, invalid, key + columns)}"]

    def _invalid_months(self, frame):
        invalid = ~frame["mes"].between(1, 12)
        if not invalid.any():
            return []
        return [f"{int(invalid.sum())} filas con mes fuera de 1–12; por ejemplo {sorted(frame.loc[invalid, 'mes'].unique().tolist())[:SAMPLE_SIZE]}"]

    def _annual_month(self, annual):
        invalid = annual["mes"].ne(self.annual_month)
        if not invalid.any():
            return []
        return [f"{int(invalid.sum())} filas anuales con un mes distinto de {self.annual_month}; por ejemplo {self._sample(annual, invalid, PENSIONES_KEY)}"]

    def _dates(self, frame, today, last_day):
        fecha = frame["fecha_referencia"]
        expected_day = pd.to_datetime(fecha.astype(str)).dt.days_in_month if last_day else 1
        inconsistent = fecha.dt.year.ne(frame["anyo"]) | fecha.dt.month.ne(frame["mes"]) | fecha.dt.day.ne(expected_day)
        future = fecha.gt(today)
        problems = []
        if inconsistent.any():
            problems.append(f"{int(inconsistent.sum())} filas con anyo o mes distintos de fecha_referencia; por ejemplo {self._sample(frame, inconsistent, ['anyo', 'mes', 'fecha_referencia'])}")
        if future.any():
            problems.append(f"{int(future.sum())} filas con fecha_referencia posterior a {today}; por ejemplo {self._sample(frame, future, ['anyo', 'mes', 'fecha_referencia'])}")
        return problems

    def _duplicated(self, frame, key):
        duplicated = frame.duplicated(key, keep=False)
        if not duplicated.any():
            return []
        return [f"{int(duplicated.sum())} filas repiten la clave {key}; por ejemplo {self._sample(frame, duplicated, key)}"]

    def _classes_above_total(self, frame):
        above = frame[list(PENSION_CLASSES)].gt(frame["total_pensiones"], axis=0).fillna(False).any(axis=1)
        if not above.any():
            return []
        return [f"{int(above.sum())} filas con una clase mayor que total_pensiones; por ejemplo {self._sample(frame, above, PENSIONES_KEY)}"]

    def _classes_sum(self, frame):
        difference = frame[list(PENSION_CLASSES)].sum(axis=1, min_count=len(PENSION_CLASSES)) - frame["total_pensiones"]
        mismatched = difference.ne(0).fillna(False)
        if not mismatched.any():
            return []
        sample = frame.loc[mismatched, PENSIONES_KEY].assign(diferencia=difference[mismatched]).head(SAMPLE_SIZE).to_dict("records")
        return [f"{int(mismatched.sum())} filas cuyas clases no suman total_pensiones; por ejemplo {sample}"]

    def _annual_matches_monthly(self, evaluation, annual, monthly):
        reference = monthly[monthly["mes"].eq(self.annual_month)]
        pairs = annual.merge(reference, on=["territorio", "anyo"], suffixes=("_anual", "_mensual"))
        evaluation.metrics["anyos_anual_contrastados_con_mensual"] = sorted(pairs["anyo"].astype(int).tolist())
        mismatched = pd.Series(False, index=pairs.index)
        for column in PENSION_COUNTS:
            mismatched |= pairs[f"{column}_anual"].ne(pairs[f"{column}_mensual"]).fillna(True)
        if not mismatched.any():
            return []
        return [f"{int(mismatched.sum())} años cuyo dato anual no coincide con el mensual del mes {self.annual_month}: {sorted(pairs.loc[mismatched, 'anyo'].tolist())}"]

    def _coverage(self, evaluation, name, observed, expected):
        present = expected & observed
        completeness = len(present) / len(expected) if expected else 0.0
        missing = sorted(expected - observed)
        evaluation.metrics[name] = {
            "esperados": len(expected),
            "presentes": len(present),
            "completitud": round(completeness, 6),
            "minimo": self.min_completeness,
            "faltantes": [str(value) for value in missing],
            "desde": str(min(expected)) if expected else None,
            "hasta": str(max(expected)) if expected else None,
        }
        if completeness >= self.min_completeness:
            return []
        return [f"completitud temporal {completeness:.2%} por debajo de {self.min_completeness:.0%}; faltan {[str(value) for value in missing[:SAMPLE_SIZE]]}"]

    def _months(self, start, end, frame):
        observed = self._observed_months(frame)
        last = max([pd.Period(end, "M")] + list(observed))
        return set(pd.period_range(pd.Period(start, "M"), last, freq="M"))

    def _years(self, start, end, frame):
        last = max([int(end)] + frame["anyo"].astype(int).tolist())
        return set(range(int(start), last + 1))

    def _observed_months(self, frame):
        return {pd.Period(year=int(year), month=int(month), freq="M") for year, month in zip(frame["anyo"], frame["mes"]) if 1 <= int(month) <= 12}

    def _sample(self, frame, mask, columns):
        return frame.loc[mask, columns].head(SAMPLE_SIZE).to_dict("records")
