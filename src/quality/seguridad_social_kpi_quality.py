from src.indicators.kpi_ratio_schema import KpiRatioSchema

KPI_KEY = ["anyo", "territorio", "metodologia_ratio"]
SAMPLE_SIZE = 5
RULES = (
    ("valores_no_nulos", "SS-KPI: todos los años tienen ratio"),
    ("fraccion_nulos", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage"),
    ("denominadores_positivos", "SS-KPI: total_pensiones mayor que cero (división por cero rechazada)"),
    ("ratio_positivo", "SS-KPI: ratio mayor que cero"),
    ("ratio_coherente", "SS-KPI: ratio igual a total_afiliados / total_pensiones"),
    ("metodologia_homogenea", "SS-KPI: numerador y denominador son stocks del mes de referencia en todos los años"),
    ("clave_unica", "SS-KPI: una fila por año, territorio y metodología"),
    ("cobertura_anual", "SS-KPI: años con ratio dentro de la cobertura esperada >= quality.min_temporal_completeness"),
    ("pension_media_coherente", "SS-KPI: pension_media_eur = importe_nomina_miles_eur × 1000 / total_pensiones, dentro de 100-5000 EUR"),
)


class SeguridadSocialKpiQuality:
    def __init__(self, kpi_config, quality_config):
        self.schema = KpiRatioSchema()
        self.epsilon = kpi_config["float_epsilon"]
        self.month = kpi_config["reference_month"]
        self.expected_years = set(range(kpi_config["expected_start"], kpi_config["expected_end"] + 1))
        self.max_null_fraction = quality_config["max_null_percentage"]
        self.min_completeness = quality_config["min_temporal_completeness"]

    def evaluate(self, computed, evaluation):
        frame = computed["frame"]
        evaluation.metrics["filas"] = len(frame)
        evaluation.metrics.update(computed["unmatched"])
        if not evaluation.check("esquema", "QLT-001: columnas, tipos, nulos obligatorios y dominios de KpiRatioSchema", self.schema.problems(frame)):
            for name, description in RULES:
                evaluation.skip(name, description, "el esquema no se cumple")
            return evaluation
        problems = {
            "valores_no_nulos": self._flagged(frame, frame["ratio_cotizantes_pensionistas"].isna(), "años sin ratio"),
            "fraccion_nulos": evaluation.null_fractions(frame, self.max_null_fraction, ()),
            "denominadores_positivos": self._flagged(frame, frame["total_pensiones"].le(0), "años con total_pensiones no positivo"),
            "ratio_positivo": self._flagged(frame, frame["ratio_cotizantes_pensionistas"].le(0).fillna(False), "años con ratio no positivo"),
            "ratio_coherente": self._incoherent(frame),
            "metodologia_homogenea": self._methodology(frame),
            "clave_unica": self._flagged(frame, frame.duplicated(KPI_KEY, keep=False), f"filas que repiten la clave {KPI_KEY}"),
            "cobertura_anual": self._coverage(evaluation, frame),
            "pension_media_coherente": self._average_pension(frame),
        }
        for name, description in RULES:
            evaluation.check(name, description, problems[name])
        return evaluation

    def _flagged(self, frame, mask, label):
        if not mask.any():
            return []
        return [f"{int(mask.sum())} {label}; por ejemplo {frame.loc[mask, KPI_KEY].head(SAMPLE_SIZE).to_dict('records')}"]

    def _incoherent(self, frame):
        expected = frame["total_afiliados"] / frame["total_pensiones"].where(frame["total_pensiones"].gt(0))
        difference = (frame["ratio_cotizantes_pensionistas"] - expected).abs()
        return self._flagged(frame, difference.gt(self.epsilon), "ratios distintos de total_afiliados / total_pensiones")

    def _average_pension(self, frame):
        if frame["importe_nomina_miles_eur"].isna().all():
            return []
        expected = frame["importe_nomina_miles_eur"] * 1000 / frame["total_pensiones"].where(frame["total_pensiones"].gt(0))
        incoherent = (frame["pension_media_eur"] - expected).abs().gt(self.epsilon * expected.abs().clip(lower=1)).fillna(True)
        outside = ~frame["pension_media_eur"].between(100, 5000)
        problems = self._flagged(frame, incoherent, "pensiones medias distintas de importe × 1000 / total_pensiones")
        return problems + self._flagged(frame, outside & ~incoherent, "pensiones medias fuera de 100-5000 EUR")

    def _methodology(self, frame):
        inconsistent = (
            frame["mes_referencia"].ne(self.month)
            | frame["fecha_referencia_afiliados"].dt.month.ne(self.month)
            | frame["fecha_referencia_pensiones"].dt.month.ne(self.month)
            | frame["fecha_referencia_afiliados"].dt.year.ne(frame["anyo"])
            | frame["fecha_referencia_pensiones"].dt.year.ne(frame["anyo"])
        )
        problems = self._flagged(frame, inconsistent, f"años cuyo numerador o denominador no es del mes {self.month}")
        if frame["metodologia_ratio"].nunique() > 1:
            problems.append(f"la serie mezcla metodologías: {sorted(frame['metodologia_ratio'].unique())}")
        return problems

    def _coverage(self, evaluation, frame):
        observed = set(frame.loc[frame["ratio_cotizantes_pensionistas"].notna(), "anyo"].astype(int))
        present = self.expected_years & observed
        completeness = len(present) / len(self.expected_years)
        evaluation.metrics["cobertura_anual"] = {
            "esperados": len(self.expected_years),
            "presentes": len(present),
            "completitud": round(completeness, 6),
            "minimo": self.min_completeness,
            "faltantes": sorted(self.expected_years - observed),
            "anyos_con_ratio": sorted(observed),
        }
        if completeness >= self.min_completeness:
            return []
        return [f"cobertura anual {completeness:.2%} por debajo de {self.min_completeness:.0%}; faltan {sorted(self.expected_years - observed)[:SAMPLE_SIZE]}"]
