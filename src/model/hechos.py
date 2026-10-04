import pandas as pd

from src.indicators.demografia_kpis import AGE_GROUPS, DemografiaKpis
from src.model.modelo_schema import OBSERVED_STATES, TOTAL_AGE_GROUP, FactIndicadoresSchema

NATURAL_KEY = ["anyo", "territorio", "sexo", "grupo_edad", "indicador"]
NATURAL_COLUMNS = NATURAL_KEY + ["valor", "unidad", "estado_dato", "fuente", "metodologia", "dataset_origen", "run_id_origen"]
SILVER_PUBLISHED = {
    "nacimientos": "ine",
    "defunciones": "ine",
    "saldo_migratorio_exterior": "ine",
    "indicador_coyuntural_fecundidad": "ine",
    "esperanza_vida_nacimiento": "ine",
    "esperanza_vida_65": "ine",
}
PENSION_COLUMNS = {
    "ratio_cotizantes_pensionistas": "ratio_cotizantes_pensionistas",
    "total_pensiones": "total_pensiones",
    "importe_nomina_miles_eur": "importe_nomina_pensiones",
    "pension_media_eur": "pension_media_mensual",
}
MACRO_METRICS = ("pib", "gasto_pensiones")
SORT_KEYS = ["indicador_key", "sexo_key", "grupo_edad_key", "tiempo_key"]


class Hechos:
    """Integra en formato largo los datos OBSERVADOS de Plata y de la capa de indicadores.

    - No calcula KPIs: los toma de la capa de indicadores (o del INE cuando el indicador es publicado).
    - Solo agrega la población por grupo de edad y sexo, con la misma clasificación que alimenta los KPIs
      (`DemografiaKpis.age_groups`), para que numeradores y denominadores sean auditables en el modelo.
    - No interpola ni rellena: un año sin dato publicado no tiene fila.
    """

    def __init__(self, config):
        self.catalog = config["modelo"]["indicators"]
        self.age_classifier = DemografiaKpis(config["indicadores"]["demografia"])
        self.schema = FactIndicadoresSchema()

    def integrate(self, inputs):
        silver = inputs["stg_poblacion_anual"]
        detail = silver["frame"]
        observed = detail[~detail["es_control"] & detail["estado_dato"].isin(OBSERVED_STATES)]
        population = self._population(observed[observed["metrica"].eq("poblacion")], silver["run_id"])
        parts = {
            "poblacion": population["frame"],
            "publicados_ine": self._published(observed[observed["metrica"].isin(SILVER_PUBLISHED)], silver["run_id"]),
            "kpis_demograficos": self._demographic_kpis(inputs["kpis_demograficos"]),
            "afiliados": self._affiliates(inputs["stg_afiliados_mensual"]),
            "pensiones": self._pensions(inputs["kpi_ratio_sostenibilidad_anual"]),
            "integrados": self._integrated(inputs["kpis_integrados_anual"]),
            "macro": self._macro(inputs["stg_macro_anual"]),
        }
        natural = pd.concat(parts.values(), ignore_index=True)
        unknown = sorted(set(natural["indicador"]) - set(self.catalog))
        if unknown:
            raise ValueError(f"Indicadores sin declarar en modelo.indicators: {', '.join(unknown)}.")
        return {"frame": natural, "age_groups": population["age_groups"], "rows_by_part": {name: len(part) for name, part in parts.items()}}

    def assign_keys(self, natural, dimensions, gold_run_id, generated_at):
        maps = {
            "tiempo_key": ("anyo", dimensions["dim_tiempo"].set_index("anyo")["tiempo_key"]),
            "territorio_key": ("territorio", dimensions["dim_territorio"].set_index("codigo_territorio")["territorio_key"]),
            "sexo_key": ("sexo", dimensions["dim_sexo"].set_index("codigo_sexo")["sexo_key"]),
            "grupo_edad_key": ("grupo_edad", dimensions["dim_grupo_edad"].set_index("codigo_grupo")["grupo_edad_key"]),
            "indicador_key": ("indicador", dimensions["dim_indicador"].set_index("codigo_indicador")["indicador_key"]),
            "fuente_key": ("fuente", dimensions["dim_fuente"].set_index("codigo_fuente")["fuente_key"]),
        }
        frame = natural.copy()
        for key, (column, mapping) in maps.items():
            frame[key] = frame[column].map(mapping).fillna(-1).astype("int64")
        frame["gold_run_id"] = gold_run_id
        frame["fecha_generacion"] = pd.Timestamp(generated_at)
        frame = frame[self.schema.columns()].astype(self.schema.dtypes)
        return frame.sort_values(SORT_KEYS, ignore_index=True)

    def _frame(self, anyo, territorio, indicador, valor, unidad, estado, fuente, metodologia, dataset, run_id, sexo="total", grupo=TOTAL_AGE_GROUP):
        frame = pd.DataFrame(
            {
                "anyo": pd.Series(anyo).astype("int64").to_numpy(),
                "territorio": pd.Series(territorio).to_numpy() if not isinstance(territorio, str) else territorio,
                "sexo": pd.Series(sexo).to_numpy() if not isinstance(sexo, str) else sexo,
                "grupo_edad": grupo,
                "indicador": pd.Series(indicador).to_numpy() if not isinstance(indicador, str) else indicador,
                "valor": pd.Series(valor).astype("float64").to_numpy(),
                "unidad": pd.Series(unidad).to_numpy() if not isinstance(unidad, str) else unidad,
                "estado_dato": pd.Series(estado).to_numpy() if not isinstance(estado, str) else estado,
                "fuente": fuente,
                "metodologia": pd.Series(metodologia).to_numpy() if not isinstance(metodologia, str) else metodologia,
                "dataset_origen": dataset,
                "run_id_origen": run_id,
            }
        )
        return frame[NATURAL_COLUMNS]

    def _population(self, population, run_id):
        units = population["unidad"].unique().tolist()
        if len(units) > 1:
            raise ValueError(f"La población de detalle de Plata mezcla unidades ({units}); no se puede sumar por grupo de edad.")
        frames = []
        all_groups = []
        for sex in ("total", "hombres", "mujeres"):
            groups = self.age_classifier.age_groups(population[population["sexo"].eq(sex)])
            groups = groups.assign(sexo=sex).rename(columns={"total_detalle": TOTAL_AGE_GROUP})
            all_groups.append(groups)
            melted = groups.melt(
                id_vars=["anyo", "territorio", "estado_dato", "sexo"], value_vars=[TOTAL_AGE_GROUP, *AGE_GROUPS], var_name="grupo_edad", value_name="valor"
            )
            frames.append(melted)
        melted = pd.concat(frames, ignore_index=True)
        frame = pd.DataFrame(
            {
                "anyo": melted["anyo"].astype("int64"),
                "territorio": melted["territorio"],
                "sexo": melted["sexo"],
                "grupo_edad": melted["grupo_edad"],
                "indicador": "poblacion",
                "valor": melted["valor"].astype("float64"),
                "unidad": units[0] if units else "personas",
                "estado_dato": melted["estado_dato"],
                "fuente": "ine",
                "metodologia": "suma_edades_simples_ine_56934",
                "dataset_origen": "stg_poblacion_anual",
                "run_id_origen": run_id,
            }
        )
        return {"frame": frame[NATURAL_COLUMNS], "age_groups": pd.concat(all_groups, ignore_index=True)}

    def _published(self, events, run_id):
        return self._frame(
            events["anyo"], events["territorio"], events["metrica"], events["valor"], events["unidad"], events["estado_dato"],
            "ine", "ine_" + events["tabla_id"].astype(str), "stg_poblacion_anual", run_id, sexo=events["sexo"],
        )

    def _demographic_kpis(self, kpis):
        frame = kpis["frame"]
        observed = frame[frame["estado_dato"].isin(OBSERVED_STATES)]
        return self._frame(
            observed["anyo"], observed["territorio"], observed["indicador"], observed["valor"], observed["unidad"], observed["estado_dato"],
            "ine", "kpis_demograficos", "kpis_demograficos", kpis["run_id"],
        )

    def _affiliates(self, afiliados):
        frame = afiliados["frame"]
        december = frame[frame["mes"].eq(12) & frame["total_afiliados"].notna()]
        return self._frame(
            december["anyo"], december["territorio"], "total_afiliados", december["total_afiliados"], self.catalog["total_afiliados"]["unidad"],
            december["estado_dato"], "seguridad_social", "stock_31_diciembre", "stg_afiliados_mensual", afiliados["run_id"],
        )

    def _pensions(self, ratio):
        frame = ratio["frame"]
        parts = []
        for column, indicator in PENSION_COLUMNS.items():
            present = frame[frame[column].notna()]
            parts.append(
                self._frame(
                    present["anyo"], present["territorio"], indicator, present[column], self.catalog[indicator]["unidad"], present["estado_dato"],
                    "seguridad_social", present["metodologia_ratio"], "kpi_ratio_sostenibilidad_anual", ratio["run_id"],
                )
            )
        return pd.concat(parts, ignore_index=True)

    def _integrated(self, integrated):
        frame = integrated["frame"]
        sources = frame["indicador"].map(lambda indicator: self.catalog[indicator]["fuente"])
        parts = []
        for source, group in frame.groupby(sources):
            parts.append(
                self._frame(
                    group["anyo"], group["territorio"], group["indicador"], group["valor"], group["unidad"], group["estado_dato"],
                    source, group["metodologia"], "kpis_integrados_anual", integrated["run_id"],
                )
            )
        return pd.concat(parts, ignore_index=True)

    def _macro(self, macro):
        frame = macro["frame"]
        selected = frame[frame["metrica"].isin(MACRO_METRICS)]
        return self._frame(
            selected["anyo"], selected["territorio"], selected["metrica"], selected["valor"], selected["unidad"], selected["estado_dato"],
            "eurostat", "eurostat_" + selected["codigo_eurostat"].astype(str), "stg_macro_anual", macro["run_id"],
        )
