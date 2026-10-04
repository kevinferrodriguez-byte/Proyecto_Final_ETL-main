import pandas as pd

from src.indicators.demografia_kpis import AGE_GROUPS
from src.model.modelo_schema import OBSERVED_STATES, TOTAL_AGE_GROUP
from src.quality.checks import SAMPLE_SIZE, compare, compare_absolute, dimension_keys, flagged, foreign_keys, modified_zscore_outliers

FACT_KEY = ["tiempo_key", "territorio_key", "sexo_key", "grupo_edad_key", "indicador_key"]
DIMENSION_KEYS = {
    "dim_tiempo": ("tiempo_key", "anyo"),
    "dim_territorio": ("territorio_key", "codigo_territorio"),
    "dim_sexo": ("sexo_key", "codigo_sexo"),
    "dim_grupo_edad": ("grupo_edad_key", "codigo_grupo"),
    "dim_fuente": ("fuente_key", "codigo_fuente"),
    "dim_indicador": ("indicador_key", "codigo_indicador"),
}
FOREIGN_KEYS = {
    "tiempo_key": "dim_tiempo",
    "territorio_key": "dim_territorio",
    "sexo_key": "dim_sexo",
    "grupo_edad_key": "dim_grupo_edad",
    "indicador_key": "dim_indicador",
    "fuente_key": "dim_fuente",
}
RULES = (
    ("dimensiones_esquema", "MOD-01: columnas, tipos, nulos y dominios de cada dimensión"),
    ("dimensiones_clave_unica", "MOD-02: clave sustituta y código natural únicos en cada dimensión"),
    ("tiempo_continuo", "MOD-03: dim_tiempo sin huecos y con todos los años de los hechos"),
    ("grupos_edad_convencion", "MOD-04: grupos de edad contiguos desde 0 y coherentes con indicadores.demografia.age_groups"),
    ("catalogo_completo", "MOD-05: todo indicador de los hechos está en dim_indicador y los 8 KPIs tienen datos"),
    ("fact_esquema", "MOD-06: columnas, tipos, nulos y dominios de fact_indicadores_anual"),
    ("fact_clave_unica", "MOD-07: una fila por año, territorio, sexo, grupo de edad e indicador"),
    ("fact_fk_validas", "MOD-08: integridad referencial (toda clave foránea existe en su dimensión)"),
    ("fact_filas_conservadas", "MOD-09: cada fila de origen aparece exactamente una vez (conteo antes = después)"),
    ("fact_solo_observado", "MOD-10: el modelo solo contiene datos observados o provisionales (las proyecciones van a la capa de escenarios)"),
    ("fact_rangos_validos", "MOD-11: cada indicador dentro de su rango plausible del catálogo"),
    ("fact_desagregacion_valida", "MOD-12: cada indicador solo usa las desagregaciones (sexo, grupo de edad) declaradas en el catálogo"),
    ("fact_unidad_homogenea", "MOD-13: una unidad por indicador y metodología"),
    ("fact_coherencia", "MOD-14: KPIs coherentes con sus componentes dentro del modelo (fórmulas del catálogo)"),
    ("sexos_suman_total", "MOD-15: población de hombres + mujeres = total por grupo de edad (tolerancia de redondeo INE: modelo.tolerancia_suma_sexos_personas)"),
    ("completitud_vertical", "QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage"),
    ("completitud_temporal", "QLT-003 / KR 1.2: años presentes / cobertura del catálogo >= quality.min_temporal_completeness"),
    ("panel_esquema", "MOD-16: columnas, tipos y nulos de dm_panel_anual"),
    ("panel_conciliado", "MOD-17: cada celda de dm_panel_anual coincide con su fila de fact_indicadores_anual"),
)
WARNINGS = (
    ("consistencia_poblacion_ine_eurostat", "MOD-W1: población INE a 1 de enero frente a Eurostat demo_pjan (diferencia relativa máxima configurada)"),
    ("atipicos", "MOD-W2: variaciones interanuales atípicas en series observadas (z-score modificado; solo advierte)"),
)
STRUCTURE_KPIS = ("indice_envejecimiento", "tasa_dependencia", "tasa_dependencia_mayores", "porcentaje_mayores_65")


class ModeloQuality:
    def __init__(self, config):
        model = config["modelo"]
        self.catalog = model["indicators"]
        self.epsilon = model["float_epsilon"]
        self.sex_tolerance = model["tolerancia_suma_sexos_personas"]
        self.outliers = model["outliers"]
        self.population_tolerance = model["consistencia_poblacion"]["max_diferencia_relativa"]
        self.limits = config["indicadores"]["demografia"]["age_groups"]
        self.lag = config["indicadores"]["integrados"]["afiliacion_desfase_poblacion_anyos"]
        self.max_null_fraction = config["quality"]["max_null_percentage"]
        self.min_completeness = config["quality"]["min_temporal_completeness"]

    def evaluate(self, model, evaluation):
        dimensions, fact, panel, schemas = model["dimensions"], model["fact"], model["panel"], model["schemas"]
        evaluation.metrics["filas"] = {name: len(frame) for name, frame in {**dimensions, "fact_indicadores_anual": fact, "dm_panel_anual": panel}.items()}
        schema_problems = {
            "dimensiones_esquema": [f"{name}: {problem}" for name, frame in dimensions.items() for problem in schemas[name].problems(frame)],
            "fact_esquema": schemas["fact_indicadores_anual"].problems(fact),
            "panel_esquema": schemas["dm_panel_anual"].problems(panel),
        }
        if any(schema_problems.values()):
            for name, description in RULES:
                if name in schema_problems:
                    evaluation.check(name, description, schema_problems[name])
                else:
                    evaluation.skip(name, description, "algún esquema del modelo no se cumple")
            for name, description in WARNINGS:
                evaluation.skip(name, description, "algún esquema del modelo no se cumple")
            return evaluation
        wide = self.denormalized(fact, dimensions)
        problems = {
            **schema_problems,
            "dimensiones_clave_unica": dimension_keys(dimensions, DIMENSION_KEYS),
            "tiempo_continuo": self._time(dimensions["dim_tiempo"], fact),
            "grupos_edad_convencion": self._age_groups(dimensions["dim_grupo_edad"]),
            "catalogo_completo": self._catalog(wide, dimensions["dim_indicador"]),
            "fact_clave_unica": flagged(fact, fact.duplicated(FACT_KEY, keep=False), FACT_KEY, f"filas repiten la clave {FACT_KEY}"),
            "fact_fk_validas": foreign_keys(fact, dimensions, FOREIGN_KEYS, DIMENSION_KEYS, FACT_KEY),
            "fact_filas_conservadas": self._conserved(evaluation, fact, model["expected_rows"]),
            "fact_solo_observado": flagged(fact, ~fact["estado_dato"].isin(OBSERVED_STATES), FACT_KEY, "filas no observadas"),
            "fact_rangos_validos": self._ranges(wide),
            "fact_desagregacion_valida": self._disaggregation(wide),
            "fact_unidad_homogenea": self._units(wide),
            "fact_coherencia": self._coherence(wide),
            "sexos_suman_total": self._sexes(wide),
            "completitud_vertical": evaluation.null_fractions(fact, self.max_null_fraction, ()),
            "completitud_temporal": self._temporal(evaluation, wide),
            "panel_conciliado": self._panel(wide, panel),
        }
        for name, description in RULES:
            evaluation.check(name, description, problems[name])
        evaluation.warn(*WARNINGS[0], self._population_consistency(evaluation, wide, model["control_population"]))
        evaluation.warn(*WARNINGS[1], self._outliers(evaluation, wide))
        return evaluation

    def denormalized(self, fact, dimensions):
        frame = fact.merge(dimensions["dim_tiempo"][["tiempo_key", "anyo"]], on="tiempo_key", how="left")
        frame = frame.merge(dimensions["dim_sexo"][["sexo_key", "codigo_sexo"]], on="sexo_key", how="left")
        frame = frame.merge(dimensions["dim_grupo_edad"][["grupo_edad_key", "codigo_grupo"]], on="grupo_edad_key", how="left")
        return frame.merge(dimensions["dim_indicador"][["indicador_key", "codigo_indicador"]], on="indicador_key", how="left")

    def _time(self, time, fact):
        years = time["anyo"].tolist()
        problems = []
        if not years or years != list(range(years[0], years[-1] + 1)):
            problems.append("dim_tiempo tiene huecos, está desordenada o vacía")
        if time["tiempo_key"].ne(time["anyo"]).any():
            problems.append("tiempo_key no coincide con anyo")
        missing = sorted(set(fact["tiempo_key"]) - set(time["tiempo_key"]))
        if missing:
            problems.append(f"años de los hechos ausentes de dim_tiempo: {missing[:SAMPLE_SIZE]}")
        return problems

    def _age_groups(self, groups):
        expected = {
            TOTAL_AGE_GROUP: (0, None),
            "menores_16": (0, self.limits["young_max_age"]),
            "activos_16_64": (self.limits["working_min_age"], self.limits["working_max_age"]),
            "mayores_65": (self.limits["elderly_min_age"], None),
        }
        actual = {row.codigo_grupo: (int(row.edad_min), None if pd.isna(row.edad_max) else int(row.edad_max)) for row in groups.itertuples()}
        problems = [f"grupo {code}: {actual.get(code)} en lugar de {bounds}" for code, bounds in expected.items() if actual.get(code) != bounds]
        if self.limits["working_min_age"] != self.limits["young_max_age"] + 1 or self.limits["elderly_min_age"] != self.limits["working_max_age"] + 1:
            problems.append(f"los tramos de edad no son contiguos: {self.limits}")
        return problems

    def _catalog(self, wide, indicators):
        problems = []
        unknown = sorted(set(wide["codigo_indicador"].dropna()) - set(indicators["codigo_indicador"]))
        if unknown:
            problems.append(f"indicadores de los hechos ausentes de dim_indicador: {unknown}")
        kpis = indicators.loc[indicators["tipo_indicador"].eq("kpi"), "codigo_indicador"]
        empty = sorted(set(kpis) - set(wide["codigo_indicador"]))
        if empty:
            problems.append(f"KPIs del catálogo sin datos en el modelo: {empty}")
        if len(kpis) != 8:
            problems.append(f"el catálogo declara {len(kpis)} KPIs; el proyecto define 8")
        return problems

    def _conserved(self, evaluation, fact, expected_rows):
        evaluation.metrics["filas_por_origen"] = expected_rows
        expected = sum(expected_rows.values())
        return [] if len(fact) == expected else [f"la tabla de hechos tiene {len(fact)} filas y los orígenes suman {expected} ({expected_rows})"]

    def _ranges(self, wide):
        problems = []
        for indicator, spec in self.catalog.items():
            selected = wide["codigo_indicador"].eq(indicator)
            outside = selected & ~wide["valor"].between(spec["rango"]["min"], spec["rango"]["max"])
            problems.extend(flagged(wide, outside, ["anyo", "codigo_indicador", "codigo_sexo", "codigo_grupo", "valor"], f"valores de {indicator} fuera de [{spec['rango']['min']}, {spec['rango']['max']}]"))
        return problems

    def _disaggregation(self, wide):
        problems = []
        for indicator, spec in self.catalog.items():
            selected = wide["codigo_indicador"].eq(indicator)
            if "sexo" not in spec["desagregaciones"]:
                problems.extend(flagged(wide, selected & wide["codigo_sexo"].ne("total"), ["anyo", "codigo_indicador", "codigo_sexo"], f"filas de {indicator} desagregadas por sexo sin declararlo"))
            if "grupo_edad" not in spec["desagregaciones"]:
                problems.extend(flagged(wide, selected & wide["codigo_grupo"].ne(TOTAL_AGE_GROUP), ["anyo", "codigo_indicador", "codigo_grupo"], f"filas de {indicator} desagregadas por edad sin declararlo"))
        return problems

    def _units(self, wide):
        units = wide.groupby(["codigo_indicador", "metodologia"])["unidad"].nunique()
        mixed = units[units.gt(1)]
        return [f"{indicator} ({method}) mezcla unidades" for indicator, method in mixed.index]

    def _coherence(self, wide):
        problems = []
        index = ["territorio_key", "anyo"]
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
        problems.extend(compare("poblacion total = suma de grupos", total, population[list(AGE_GROUPS)].sum(axis=1), self.epsilon))
        for indicator, formula in expected.items():
            if indicator in values:
                problems.extend(compare(indicator, values[indicator], formula, self.epsilon))
        pairs = {
            "saldo_vegetativo": ("nacimientos", "defunciones", lambda a, b: a - b),
            "ratio_cotizantes_pensionistas": ("total_afiliados", "total_pensiones", lambda a, b: a / b.where(b.gt(0))),
            "pension_media_mensual": ("importe_nomina_pensiones", "total_pensiones", lambda a, b: a * 1000 / b.where(b.gt(0))),
            "gasto_pensiones_pib": ("gasto_pensiones", "pib", lambda a, b: a / b.where(b.gt(0)) * 100),
        }
        for indicator, (left, right, formula) in pairs.items():
            if {indicator, left, right} <= set(values.columns):
                problems.extend(compare(indicator, values[indicator], formula(values[left], values[right]), self.epsilon))
        if {"tasa_afiliacion_16_64", "total_afiliados"} <= set(values.columns):
            lagged = working.rename("poblacion_16_64").reset_index()
            lagged["anyo"] = lagged["anyo"] - self.lag
            working_lagged = lagged.set_index(index)["poblacion_16_64"]
            problems.extend(compare("tasa_afiliacion_16_64", values["tasa_afiliacion_16_64"], values["total_afiliados"] / working_lagged.where(working_lagged.gt(0)) * 100, self.epsilon))
        return problems

    def _sexes(self, wide):
        population = wide[wide["codigo_indicador"].eq("poblacion")].pivot_table(index=["territorio_key", "anyo", "codigo_grupo"], columns="codigo_sexo", values="valor", aggfunc="first")
        if not {"total", "hombres", "mujeres"} <= set(population.columns):
            return ["faltan series de población por sexo"]
        return compare_absolute("poblacion hombres + mujeres = total", population["total"], population["hombres"] + population["mujeres"], self.sex_tolerance)

    def _temporal(self, evaluation, wide):
        coverage = []
        problems = []
        present = wide.groupby(["codigo_indicador", "codigo_sexo", "codigo_grupo"])["anyo"].apply(set)
        for indicator, spec in self.catalog.items():
            expected = set(range(spec["cobertura"]["desde"], spec["cobertura"]["hasta"] + 1))
            sexes = ["total", "hombres", "mujeres"] if "sexo" in spec["desagregaciones"] else ["total"]
            groups = [TOTAL_AGE_GROUP, *AGE_GROUPS] if "grupo_edad" in spec["desagregaciones"] else [TOTAL_AGE_GROUP]
            for sex in sexes:
                for group in groups:
                    years = present.get((indicator, sex, group), set())
                    found = expected & years
                    completeness = len(found) / len(expected)
                    coverage.append(
                        {
                            "indicador": indicator,
                            "tipo": spec["tipo"],
                            "sexo": sex,
                            "grupo_edad": group,
                            "esperado_desde": min(expected),
                            "esperado_hasta": max(expected),
                            "esperados": len(expected),
                            "presentes": len(found),
                            "completitud": round(completeness, 6),
                            "faltantes": sorted(expected - years)[:SAMPLE_SIZE],
                            "fuera_de_cobertura": sorted(years - expected)[:SAMPLE_SIZE],
                        }
                    )
                    if completeness < self.min_completeness:
                        problems.append(f"{indicator} | {sex} | {group}: completitud {completeness:.2%} < {self.min_completeness:.0%}; faltan {sorted(expected - years)[:SAMPLE_SIZE]}")
        evaluation.metrics["completitud_temporal"] = coverage
        evaluation.metrics["completitud_temporal_minima"] = min((row["completitud"] for row in coverage), default=None)
        evaluation.metrics["completitud_temporal_media"] = round(sum(row["completitud"] for row in coverage) / len(coverage), 6) if coverage else None
        return problems

    def _panel(self, wide, panel):
        problems = []
        total_sex = wide[wide["codigo_sexo"].eq("total")]
        columns = [column for column in panel.columns if column not in ("tiempo_key", "anyo", "territorio_key", "tiene_datos_provisionales", "gold_run_id")]
        long = panel.melt(id_vars=["tiempo_key", "territorio_key"], value_vars=columns, var_name="columna", value_name="valor_panel").dropna(subset=["valor_panel"])
        population_columns = {"poblacion_total": TOTAL_AGE_GROUP, "poblacion_menores_16": "menores_16", "poblacion_16_64": "activos_16_64", "poblacion_65_mas": "mayores_65"}
        long["codigo_indicador"] = long["columna"].where(~long["columna"].isin(population_columns), "poblacion")
        long["codigo_grupo"] = long["columna"].map(population_columns).fillna(TOTAL_AGE_GROUP)
        merged = long.merge(total_sex, on=["tiempo_key", "territorio_key", "codigo_indicador", "codigo_grupo"], how="left")
        mismatch = merged["valor"].isna() | (merged["valor"] - merged["valor_panel"]).abs().gt(self.epsilon * merged["valor"].abs().clip(lower=1))
        problems.extend(flagged(merged, mismatch, ["tiempo_key", "columna", "valor_panel", "valor"], "celdas del panel que no coinciden con la tabla de hechos"))
        expected_cells = len(total_sex[(total_sex["codigo_grupo"].eq(TOTAL_AGE_GROUP)) | total_sex["codigo_indicador"].eq("poblacion")])
        if expected_cells != len(long):
            problems.append(f"el panel tiene {len(long)} celdas con valor y la tabla de hechos {expected_cells} filas de sexo total")
        return problems

    def _population_consistency(self, evaluation, wide, control):
        ine = wide[wide["codigo_indicador"].eq("poblacion") & wide["codigo_sexo"].eq("total") & wide["codigo_grupo"].eq(TOTAL_AGE_GROUP)].set_index("anyo")["valor"]
        eurostat = control.set_index("anyo")["valor"]
        common = ine.index.intersection(eurostat.index)
        relative = ((ine.loc[common] - eurostat.loc[common]) / eurostat.loc[common]).sort_index()
        evaluation.metrics["consistencia_poblacion_ine_eurostat"] = {
            "anyos_comparados": len(common),
            "diferencia_relativa_max": round(float(relative.abs().max()), 6) if len(common) else None,
            "diferencia_relativa_media": round(float(relative.abs().mean()), 6) if len(common) else None,
            "umbral": self.population_tolerance,
        }
        exceeded = relative[relative.abs().gt(self.population_tolerance)]
        return [f"{int(year)}: INE y Eurostat difieren un {value:+.3%}" for year, value in exceeded.items()]

    def _outliers(self, evaluation, wide):
        observed = wide[wide["estado_dato"].isin(OBSERVED_STATES)]
        result = modified_zscore_outliers(observed, ["codigo_indicador", "codigo_sexo", "codigo_grupo"], self.outliers["max_modified_zscore"], self.outliers["min_points"])
        evaluation.metrics["atipicos"] = {"metodo": "z-score modificado de variaciones interanuales", "umbral": self.outliers["max_modified_zscore"], **result}
        return [
            f"{row['codigo_indicador']} | {row['codigo_sexo']} | {row['codigo_grupo']} | {row['anyo']}: variación {row['variacion']} (z = {row['z_modificado']})"
            for row in result["hallazgos"]
        ]
