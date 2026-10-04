import pandas as pd

from src.indicators.demografia_kpis import AGE_GROUPS, DemografiaKpis
from src.model.modelo_schema import TOTAL_AGE_GROUP
from src.scenarios.escenarios_schema import DimEscenarioSchema, EscenariosMartSchema, FactProyeccionesSchema
from src.transform.demografia_schema import SCENARIOS

NATURAL_COLUMNS = ["anyo", "territorio", "escenario", "sexo", "grupo_edad", "indicador", "valor", "unidad", "metodologia", "dataset_origen", "run_id_origen"]
MAIN_KR = ("base", "optimista", "pesimista")
OFFICIAL_SOURCE = "INE · Proyecciones de Población 2026-2076 (tablas 36643 y 36652)"
SCOPE = "Escenario demográfico oficial. No es un escenario fiscal ni laboral: no se proyectan empleo, cotizaciones, PIB ni gasto."
MART_KEY = ["anyo", "territorio", "indicador", "grupo_edad"]


class Proyecciones:
    """Capa de escenarios: integra (no modela) las proyecciones oficiales de población del INE.

    Los indicadores proyectados vienen de `kpis_demograficos` (misma fórmula que los observados) y la
    población por sexo y grupo de edad de Plata. `optimista` y `pesimista` son etiquetas del KR 3.1 para los
    escenarios INE «Fecundidad y saldo migratorio altos/bajos»: se refieren a la demografía, no a las finanzas.
    """

    def __init__(self, config):
        scenarios = config["escenarios"]
        self.indicators = scenarios["indicators"]
        self.mart = scenarios["mart"]
        self.catalog = config["modelo"]["indicators"]
        self.scenario_kr = config["indicadores"]["demografia"]["escenario_kr"]
        self.ine_labels = {code: label for label, code in config["silver"]["ine"]["labels"]["escenario"].items()}
        self.age_classifier = DemografiaKpis(config["indicadores"]["demografia"])
        self.schemas = {
            "dim_escenario": DimEscenarioSchema(),
            "fact_proyecciones_demograficas": FactProyeccionesSchema(),
            "dm_escenarios_2050": EscenariosMartSchema(tuple(self.indicators), tuple(self.mart["escenario_kr"])),
        }

    def integrate(self, kpis, silver):
        detail = silver["frame"]
        projected = detail[~detail["es_control"] & detail["estado_dato"].eq("proyectado") & detail["metrica"].eq("poblacion")]
        population = self._population(projected, silver["run_id"])
        kpi_frame = kpis["frame"]
        selected = kpi_frame[kpi_frame["estado_dato"].eq("proyectado") & kpi_frame["indicador"].isin(self.indicators)]
        indicators = pd.DataFrame(
            {
                "anyo": selected["anyo"].astype("int64"),
                "territorio": selected["territorio"],
                "escenario": selected["escenario"],
                "sexo": "total",
                "grupo_edad": TOTAL_AGE_GROUP,
                "indicador": selected["indicador"],
                "valor": selected["valor"].astype("float64"),
                "unidad": selected["unidad"],
                "metodologia": "kpis_demograficos",
                "dataset_origen": "kpis_demograficos",
                "run_id_origen": kpis["run_id"],
            }
        )
        parts = {"poblacion": population["frame"], "kpis": indicators[NATURAL_COLUMNS]}
        return {"frame": pd.concat(parts.values(), ignore_index=True), "age_groups": population["age_groups"], "rows_by_part": {name: len(part) for name, part in parts.items()}}

    def dim_escenario(self, scenarios_present):
        rows = []
        for code in sorted(scenarios_present, key=SCENARIOS.index):
            kr = self.scenario_kr[code]
            label = self.ine_labels[code]
            rows.append(
                {
                    "escenario_key": SCENARIOS.index(code),
                    "codigo_escenario": code,
                    "escenario_kr": kr,
                    "etiqueta_ine": label,
                    "descripcion": f"Proyección de Población del INE, escenario «{label}»" + (f" (KR 3.1: {kr})" if kr in MAIN_KR else " (análisis de sensibilidad)"),
                    "es_escenario_principal": kr in MAIN_KR,
                    "fuente_oficial": OFFICIAL_SOURCE,
                    "alcance": SCOPE,
                }
            )
        return pd.DataFrame(rows).astype(self.schemas["dim_escenario"].dtypes)

    def assign_keys(self, natural, dimensions, gold_run_id, generated_at):
        maps = {
            "tiempo_key": ("anyo", dimensions["dim_tiempo"].set_index("anyo")["tiempo_key"]),
            "territorio_key": ("territorio", dimensions["dim_territorio"].set_index("codigo_territorio")["territorio_key"]),
            "escenario_key": ("escenario", dimensions["dim_escenario"].set_index("codigo_escenario")["escenario_key"]),
            "sexo_key": ("sexo", dimensions["dim_sexo"].set_index("codigo_sexo")["sexo_key"]),
            "grupo_edad_key": ("grupo_edad", dimensions["dim_grupo_edad"].set_index("codigo_grupo")["grupo_edad_key"]),
            "indicador_key": ("indicador", dimensions["dim_indicador"].set_index("codigo_indicador")["indicador_key"]),
        }
        frame = natural.copy()
        for key, (column, mapping) in maps.items():
            frame[key] = frame[column].map(mapping).fillna(-1).astype("int64")
        frame["fuente_key"] = int(dimensions["dim_fuente"].set_index("codigo_fuente").loc["ine", "fuente_key"])
        frame["estado_dato"] = "proyectado"
        frame["gold_run_id"] = gold_run_id
        frame["fecha_generacion"] = pd.Timestamp(generated_at)
        schema = self.schemas["fact_proyecciones_demograficas"]
        frame = frame[schema.columns()].astype(schema.dtypes)
        return frame.sort_values(["indicador_key", "escenario_key", "sexo_key", "grupo_edad_key", "tiempo_key"], ignore_index=True)

    def mart_2050(self, natural, observed_last, gold_run_id):
        in_range = natural["anyo"].between(self.mart["start_year"], self.mart["end_year"])
        frame = natural[in_range & natural["sexo"].eq("total")].copy()
        frame["escenario_kr"] = frame["escenario"].map(self.scenario_kr)
        frame = frame[frame["escenario_kr"].isin(self.mart["escenario_kr"])]
        base = frame.loc[frame["escenario_kr"].eq("base"), MART_KEY + ["valor"]].rename(columns={"valor": "valor_base"})
        frame = frame.merge(base, on=MART_KEY, how="left")
        frame["diferencia_vs_base"] = frame["valor"] - frame["valor_base"]
        frame = frame.merge(observed_last, on=["territorio", "indicador", "grupo_edad"], how="left")
        frame["variacion_vs_ultimo_observado"] = frame["valor"] - frame["valor_ultimo_observado"]
        frame["gold_run_id"] = gold_run_id
        schema = self.schemas["dm_escenarios_2050"]
        frame = frame[schema.columns()].astype(schema.dtypes)
        return frame.sort_values(["indicador", "grupo_edad", "escenario_kr", "anyo"], ignore_index=True)

    def _population(self, population, run_id):
        frames = []
        all_groups = []
        for sex in ("total", "hombres", "mujeres"):
            groups = self.age_classifier.age_groups(population[population["sexo"].eq(sex)])
            groups = groups.assign(sexo=sex).rename(columns={"total_detalle": TOTAL_AGE_GROUP})
            all_groups.append(groups)
            frames.append(groups.melt(id_vars=["anyo", "territorio", "escenario", "sexo"], value_vars=[TOTAL_AGE_GROUP, *AGE_GROUPS], var_name="grupo_edad", value_name="valor"))
        melted = pd.concat(frames, ignore_index=True)
        frame = melted.assign(
            anyo=melted["anyo"].astype("int64"),
            indicador="poblacion",
            valor=melted["valor"].astype("float64"),
            unidad="personas",
            metodologia="suma_edades_simples_ine_proyecciones",
            dataset_origen="stg_poblacion_anual",
            run_id_origen=run_id,
        )
        return {"frame": frame[NATURAL_COLUMNS], "age_groups": pd.concat(all_groups, ignore_index=True)}
