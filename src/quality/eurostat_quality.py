from src.transform.eurostat.eurostat_schema import MacroSchema

KEY = ["dataset_id", "metrica", "territorio", "anyo"]
SAMPLE_SIZE = 5
RULES = (
    ("valores_no_nulos", "EUR-QLT: toda observación tiene valor"),
    ("fraccion_nulos", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage (flag_eurostat es nulo por diseño)"),
    ("no_negativos", "EUR-QLT: PIB, gasto y población no negativos"),
    ("rangos_validos", "EUR-QLT: cada métrica dentro de su rango plausible (sources.eurostat.valid_ranges)"),
    ("clave_unica", "EUR-QLT: una fila por conjunto, métrica, territorio y año"),
    ("fechas_coherentes", "EUR-QLT: fecha_referencia pertenece al año y no es futura"),
    ("unidad_homogenea", "EUR-QLT: una unidad por métrica"),
    ("completitud_temporal", "QLT-003: años presentes / esperados >= quality.min_temporal_completeness por conjunto y métrica"),
)
STRUCTURAL_NULL_COLUMNS = ("flag_eurostat",)


class EurostatQuality:
    def __init__(self, source_config, quality_config):
        self.datasets = source_config["datasets"]
        self.valid_ranges = source_config.get("valid_ranges", {})
        self.max_null_fraction = quality_config["max_null_percentage"]
        self.min_completeness = quality_config["min_temporal_completeness"]
        self.schema = MacroSchema()

    def evaluate(self, frame, evaluation, today):
        evaluation.metrics["filas"] = len(frame)
        if not evaluation.check("esquema", "QLT-001: columnas, tipos, nulos obligatorios y dominios de MacroSchema", self.schema.problems(frame)):
            for name, description in RULES:
                evaluation.skip(name, description, "el esquema no se cumple")
            return evaluation
        evaluation.metrics["filas_por_metrica"] = {str(key): int(value) for key, value in frame.groupby("metrica").size().items()}
        evaluation.metrics["flags_eurostat"] = {str(key): int(value) for key, value in frame["flag_eurostat"].value_counts().items()}
        evaluation.metrics["versiones_fuente"] = {str(key): str(value) for key, value in frame.groupby("dataset_id")["version_fuente"].first().items()}
        problems = {
            "valores_no_nulos": self._flagged(frame, frame["valor"].isna(), "observaciones sin valor"),
            "fraccion_nulos": evaluation.null_fractions(frame, self.max_null_fraction, STRUCTURAL_NULL_COLUMNS),
            "no_negativos": self._flagged(frame, frame["valor"].lt(0), "valores negativos"),
            "rangos_validos": self._ranges(frame),
            "clave_unica": self._flagged(frame, frame.duplicated(KEY, keep=False), f"filas que repiten la clave {KEY}"),
            "fechas_coherentes": self._dates(frame, today),
            "unidad_homogenea": self._units(frame),
            "completitud_temporal": self._coverage(evaluation, frame),
        }
        for name, description in RULES:
            evaluation.check(name, description, problems[name])
        return evaluation

    def _flagged(self, frame, mask, label):
        if not mask.any():
            return []
        return [f"{int(mask.sum())} {label}; por ejemplo {frame.loc[mask, KEY + ['valor']].head(SAMPLE_SIZE).to_dict('records')}"]

    def _ranges(self, frame):
        problems = []
        for metric, bounds in self.valid_ranges.items():
            selected = frame["metrica"].eq(metric)
            outside = selected & ~frame["valor"].between(bounds["min"], bounds["max"])
            problems.extend(self._flagged(frame, outside, f"valores de {metric} fuera de [{bounds['min']}, {bounds['max']}]"))
        return problems

    def _dates(self, frame, today):
        wrong_year = frame["fecha_referencia"].dt.year.ne(frame["anyo"])
        future = frame["fecha_referencia"].gt(today) & frame["tipo_medida"].eq("stock_1_enero")
        return self._flagged(frame, wrong_year, "filas cuya fecha_referencia no es del año") + self._flagged(frame, future, "stocks con fecha futura")

    def _units(self, frame):
        units = frame.groupby("metrica")["unidad"].nunique()
        mixed = units[units.gt(1)]
        return [f"la métrica {metric} mezcla unidades" for metric in mixed.index]

    def _coverage(self, evaluation, frame):
        coverage = []
        problems = []
        for dataset_id, dataset in self.datasets.items():
            periods = dataset["periods"]
            expected = set(range(periods["expected_start"], periods["expected_end"] + 1))
            for spec in dataset["metrics"]["values"].values():
                metric = spec["metrica"]
                years = set(frame.loc[frame["dataset_id"].eq(dataset_id) & frame["metrica"].eq(metric), "anyo"].astype(int))
                if not years and dataset_id not in set(frame["dataset_id"]):
                    continue
                completeness = len(expected & years) / len(expected)
                coverage.append({"dataset_id": dataset_id, "metrica": metric, "esperados": len(expected), "presentes": len(expected & years), "completitud": round(completeness, 6), "faltantes": sorted(expected - years)[:SAMPLE_SIZE], "desde": min(years) if years else None, "hasta": max(years) if years else None})
                if completeness < self.min_completeness:
                    problems.append(f"{dataset_id}.{metric}: completitud {completeness:.2%} por debajo de {self.min_completeness:.0%}; faltan {sorted(expected - years)[:SAMPLE_SIZE]}")
        evaluation.metrics["completitud_temporal"] = coverage
        return problems
