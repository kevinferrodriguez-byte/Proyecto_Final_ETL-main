from src.indicators.demografia_kpis import AGE_GROUPS
from src.model.modelo_schema import TOTAL_AGE_GROUP
from src.quality.checks import SAMPLE_SIZE, compare, compare_absolute, dimension_keys, flagged, foreign_keys

FACT_KEY = ["tiempo_key", "territorio_key", "escenario_key", "sexo_key", "grupo_edad_key", "indicador_key"]
DIMENSION_KEYS = {
    "dim_tiempo": ("tiempo_key", "anyo"),
    "dim_territorio": ("territorio_key", "codigo_territorio"),
    "dim_escenario": ("escenario_key", "codigo_escenario"),
    "dim_sexo": ("sexo_key", "codigo_sexo"),
    "dim_grupo_edad": ("grupo_edad_key", "codigo_grupo"),
    "dim_indicador": ("indicador_key", "codigo_indicador"),
    "dim_fuente": ("fuente_key", "codigo_fuente"),
}
FOREIGN_KEYS = {
    "tiempo_key": "dim_tiempo",
    "territorio_key": "dim_territorio",
    "escenario_key": "dim_escenario",
    "sexo_key": "dim_sexo",
    "grupo_edad_key": "dim_grupo_edad",
    "indicador_key": "dim_indicador",
    "fuente_key": "dim_fuente",
}
MART_KEY = ["anyo", "territorio", "escenario_kr", "grupo_edad", "indicador"]
RULES = (
    ("dim_escenario_esquema", "ESC-01: columnas, tipos y dominios de dim_escenario"),
    ("dim_escenario_mapeo", "ESC-02: escenarios presentes en los datos y escenario_kr igual a indicadores.demografia.escenario_kr"),
    ("fact_esquema", "ESC-03: columnas, tipos, nulos y dominios de fact_proyecciones_demograficas"),
    ("fact_clave_unica", "ESC-04: una fila por año, territorio, escenario, sexo, grupo de edad e indicador"),
    ("fact_fk_validas", "ESC-05: integridad referencial con dim_escenario y con las dimensiones conformadas del modelo"),
    ("fact_filas_conservadas", "ESC-06: cada fila de origen aparece exactamente una vez"),
    ("solo_indicadores_demograficos", "ESC-07: solo indicadores demográficos configurados (sin proyecciones laborales, fiscales ni macroeconómicas)"),
    ("rangos_validos", "ESC-08: valores dentro del rango plausible del catálogo"),
    ("coherencia", "ESC-09: KPIs proyectados coherentes con la población proyectada por grupo de edad en cada escenario"),
    ("sexos_suman_total", "ESC-10: población proyectada de hombres + mujeres = total"),
    ("completitud_temporal", "QLT-003: cada serie cubre todo el horizonte de las tablas proyectadas (>= quality.min_temporal_completeness)"),
    ("mart_esquema", "ESC-11: columnas, tipos, nulos y dominios de dm_escenarios_2050"),
    ("mart_clave_unica", "ESC-12: sin duplicados en la clave de dm_escenarios_2050"),
    ("mart_rango", "ESC-13: dm_escenarios_2050 cubre todos los años del rango en base, optimista y pesimista; base con diferencia 0"),
)


class EscenariosQuality:
    def __init__(self, config):
        scenarios = config["escenarios"]
        self.indicators = scenarios["indicators"]
        self.mart = scenarios["mart"]
        self.catalog = config["modelo"]["indicators"]
        self.epsilon = scenarios["float_epsilon"]
        self.sex_tolerance = scenarios["tolerancia_suma_sexos_personas"]
        self.scenario_kr = config["indicadores"]["demografia"]["escenario_kr"]
        tables = config["sources"]["ine"]["tables"]
        periods = [tables[table_id]["periods"] for table_id in scenarios["projected_tables"]]
        self.expected_years = set(range(min(p["expected_start"] for p in periods), max(p["expected_end"] for p in periods) + 1))
        self.min_completeness = config["quality"]["min_temporal_completeness"]

    def evaluate(self, layer, evaluation):
        dimensions, fact, mart, schemas = layer["dimensions"], layer["fact"], layer["mart"], layer["schemas"]
        evaluation.metrics["filas"] = {"dim_escenario": len(dimensions["dim_escenario"]), "fact_proyecciones_demograficas": len(fact), "dm_escenarios_2050": len(mart)}
        schema_problems = {
            "dim_escenario_esquema": schemas["dim_escenario"].problems(dimensions["dim_escenario"]),
            "fact_esquema": schemas["fact_proyecciones_demograficas"].problems(fact),
            "mart_esquema": schemas["dm_escenarios_2050"].problems(mart),
        }
        if any(schema_problems.values()):
            for name, description in RULES:
                if name in schema_problems:
                    evaluation.check(name, description, schema_problems[name])
                else:
                    evaluation.skip(name, description, "algún esquema de la capa de escenarios no se cumple")
            return evaluation
        wide = self._denormalized(fact, dimensions)
        problems = {
            **schema_problems,
            "dim_escenario_mapeo": self._mapping(dimensions["dim_escenario"], layer["scenarios_present"]) + dimension_keys(dimensions, DIMENSION_KEYS),
            "fact_clave_unica": flagged(fact, fact.duplicated(FACT_KEY, keep=False), FACT_KEY, f"filas repiten la clave {FACT_KEY}"),
            "fact_fk_validas": foreign_keys(fact, dimensions, FOREIGN_KEYS, DIMENSION_KEYS, FACT_KEY),
            "fact_filas_conservadas": self._conserved(evaluation, fact, layer["expected_rows"]),
            "solo_indicadores_demograficos": self._indicators(wide),
            "rangos_validos": self._ranges(wide),
            "coherencia": self._coherence(wide),
            "sexos_suman_total": self._sexes(wide),
            "completitud_temporal": self._temporal(evaluation, wide),
            "mart_clave_unica": flagged(mart, mart.duplicated(MART_KEY, keep=False), MART_KEY, f"filas repiten la clave {MART_KEY}"),
            "mart_rango": self._mart_range(mart),
        }
        for name, description in RULES:
            evaluation.check(name, description, problems[name])
        return evaluation

    def _denormalized(self, fact, dimensions):
        frame = fact.merge(dimensions["dim_tiempo"][["tiempo_key", "anyo"]], on="tiempo_key", how="left")
        frame = frame.merge(dimensions["dim_escenario"][["escenario_key", "codigo_escenario"]], on="escenario_key", how="left")
        frame = frame.merge(dimensions["dim_sexo"][["sexo_key", "codigo_sexo"]], on="sexo_key", how="left")
        frame = frame.merge(dimensions["dim_grupo_edad"][["grupo_edad_key", "codigo_grupo"]], on="grupo_edad_key", how="left")
        return frame.merge(dimensions["dim_indicador"][["indicador_key", "codigo_indicador", "dominio"]], on="indicador_key", how="left")

    def _mapping(self, scenarios, present):
        problems = []
        if set(scenarios["codigo_escenario"]) != set(present):
            problems.append(f"dim_escenario {sorted(scenarios['codigo_escenario'])} no coincide con los escenarios proyectados {sorted(present)}")
        wrong = scenarios[scenarios["escenario_kr"].ne(scenarios["codigo_escenario"].map(self.scenario_kr))]
        if not wrong.empty:
            problems.append(f"escenario_kr distinto del mapeo configurado en {wrong['codigo_escenario'].tolist()}")
        return problems

    def _conserved(self, evaluation, fact, expected_rows):
        evaluation.metrics["filas_por_origen"] = expected_rows
        expected = sum(expected_rows.values())
        return [] if len(fact) == expected else [f"la tabla tiene {len(fact)} filas y los orígenes suman {expected} ({expected_rows})"]

    def _indicators(self, wide):
        problems = []
        extra = sorted(set(wide["codigo_indicador"]) - set(self.indicators))
        if extra:
            problems.append(f"indicadores no configurados en escenarios.indicators: {extra}")
        non_demographic = sorted(set(wide.loc[wide["dominio"].ne("demografia"), "codigo_indicador"]))
        if non_demographic:
            problems.append(f"indicadores no demográficos proyectados: {non_demographic}")
        configured = [indicator for indicator in self.indicators if self.catalog[indicator]["dominio"] != "demografia"]
        if configured:
            problems.append(f"escenarios.indicators incluye indicadores no demográficos: {configured}")
        return problems

    def _ranges(self, wide):
        problems = []
        for indicator in self.indicators:
            bounds = self.catalog[indicator]["rango"]
            outside = wide["codigo_indicador"].eq(indicator) & ~wide["valor"].between(bounds["min"], bounds["max"])
            problems.extend(flagged(wide, outside, ["anyo", "codigo_escenario", "codigo_indicador", "valor"], f"valores de {indicator} fuera de rango"))
        return problems

    def _coherence(self, wide):
        index = ["territorio_key", "anyo", "codigo_escenario"]
        total_sex = wide[wide["codigo_sexo"].eq("total")]
        population = total_sex[total_sex["codigo_indicador"].eq("poblacion")].pivot_table(index=index, columns="codigo_grupo", values="valor", aggfunc="first")
        population = population.reindex(columns=[TOTAL_AGE_GROUP, *AGE_GROUPS])
        young, working, elderly, total = population["menores_16"], population["activos_16_64"], population["mayores_65"], population[TOTAL_AGE_GROUP]
        values = total_sex[total_sex["codigo_grupo"].eq(TOTAL_AGE_GROUP)].pivot_table(index=index, columns="codigo_indicador", values="valor", aggfunc="first")
        expected = {
            "indice_envejecimiento": elderly / young.where(young.gt(0)) * 100,
            "tasa_dependencia": (young + elderly) / working.where(working.gt(0)) * 100,
            "tasa_dependencia_mayores": elderly / working.where(working.gt(0)) * 100,
            "porcentaje_mayores_65": elderly / total.where(total.gt(0)) * 100,
        }
        problems = compare("poblacion total = suma de grupos", total, population[list(AGE_GROUPS)].sum(axis=1), self.epsilon)
        for indicator, formula in expected.items():
            if indicator in values:
                problems.extend(compare(indicator, values[indicator], formula, self.epsilon))
        return problems

    def _sexes(self, wide):
        population = wide[wide["codigo_indicador"].eq("poblacion")].pivot_table(index=["territorio_key", "anyo", "codigo_escenario", "codigo_grupo"], columns="codigo_sexo", values="valor", aggfunc="first")
        if not {"total", "hombres", "mujeres"} <= set(population.columns):
            return ["faltan series de población proyectada por sexo"]
        return compare_absolute("poblacion proyectada hombres + mujeres = total", population["total"], population["hombres"] + population["mujeres"], self.sex_tolerance)

    def _temporal(self, evaluation, wide):
        series = wide.groupby(["codigo_indicador", "codigo_escenario", "codigo_sexo", "codigo_grupo"])["anyo"].apply(set)
        coverage = []
        problems = []
        for key, years in series.items():
            completeness = len(self.expected_years & years) / len(self.expected_years)
            coverage.append(completeness)
            if completeness < self.min_completeness:
                problems.append(f"{' | '.join(key)}: completitud {completeness:.2%}; faltan {sorted(self.expected_years - years)[:SAMPLE_SIZE]}")
        evaluation.metrics["completitud_temporal"] = {"series": len(coverage), "minima": round(min(coverage), 6) if coverage else None, "horizonte": [min(self.expected_years), max(self.expected_years)]}
        return problems

    def _mart_range(self, mart):
        years = set(range(self.mart["start_year"], self.mart["end_year"] + 1))
        problems = []
        if set(mart["escenario_kr"]) != set(self.mart["escenario_kr"]):
            problems.append(f"escenarios {sorted(set(mart['escenario_kr']))}; se esperaban {sorted(self.mart['escenario_kr'])}")
        for key, found in mart.groupby(["escenario_kr", "indicador", "grupo_edad"])["anyo"].apply(set).items():
            if found != years:
                problems.append(f"serie {key}: faltan {sorted(years - found)[:SAMPLE_SIZE]}")
        base = mart["escenario_kr"].eq("base") & mart["diferencia_vs_base"].abs().gt(self.epsilon)
        if base.any():
            problems.append(f"{int(base.sum())} filas base con diferencia_vs_base distinta de 0")
        return problems
