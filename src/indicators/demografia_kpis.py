import numpy as np
import pandas as pd

from src.indicators.kpi_schema import KpiSchema

KEYS = ["anyo", "fecha_referencia", "territorio", "fuente", "estado_dato", "escenario"]
AGE_GROUPS = ["menores_16", "activos_16_64", "mayores_65"]
UNASSIGNED = "sin_grupo"


class DemografiaKpis:
    def __init__(self, gold_config):
        self.limits = gold_config["age_groups"]
        self.units = gold_config["units"]
        self.scenario_kr = gold_config["escenario_kr"]
        self.schema = KpiSchema()

    def compute(self, silver, silver_run_id, generated_at):
        detail = silver[silver["sexo"].eq("total") & ~silver["es_control"]]
        age_groups = self.age_groups(detail[detail["metrica"].eq("poblacion")])
        vital = self.vital_statistics(detail[detail["metrica"].isin(["nacimientos", "defunciones"])])
        indicators = pd.concat([self._structure_indicators(age_groups), self._natural_balance(vital)], ignore_index=True)
        indicators["escenario_kr"] = indicators["escenario"].map(self.scenario_kr)
        indicators["unidad"] = indicators["indicador"].map(self.units)
        indicators["silver_run_id"] = silver_run_id
        indicators["fecha_generacion"] = pd.Timestamp(generated_at)
        frame = indicators[self.schema.columns()].astype(self.schema.dtypes)
        return {"frame": frame, "age_groups": age_groups, "vital": vital}

    def age_groups(self, population):
        edad_min = population["edad_min"]
        edad_max = population["edad_max"]
        conditions = [
            edad_max.le(self.limits["young_max_age"]).fillna(False).astype(bool),
            (edad_min.ge(self.limits["working_min_age"]) & edad_max.le(self.limits["working_max_age"])).fillna(False).astype(bool),
            edad_min.ge(self.limits["elderly_min_age"]).astype(bool),
        ]
        grouped = population.assign(grupo=np.select(conditions, AGE_GROUPS, UNASSIGNED))
        sums = grouped.pivot_table(index=KEYS, columns="grupo", values="valor", aggfunc="sum", fill_value=0.0, observed=True)
        sums = sums.reindex(columns=AGE_GROUPS + [UNASSIGNED], fill_value=0.0)
        sums["filas_sin_grupo"] = grouped["grupo"].eq(UNASSIGNED).groupby([grouped[key] for key in KEYS]).sum()
        sums["total_detalle"] = grouped.groupby(KEYS)["valor"].sum()
        return sums.reset_index()

    def vital_statistics(self, events):
        vital = events.pivot_table(index=KEYS, columns="metrica", values="valor", aggfunc="sum", observed=True)
        return vital.reindex(columns=["nacimientos", "defunciones"]).reset_index()

    def _structure_indicators(self, groups):
        young = groups["menores_16"].where(groups["menores_16"].gt(0))
        working = groups["activos_16_64"].where(groups["activos_16_64"].gt(0))
        values = pd.DataFrame(
            {
                "indice_envejecimiento": groups["mayores_65"] / young * 100,
                "tasa_dependencia": (groups["menores_16"] + groups["mayores_65"]) / working * 100,
                "tasa_dependencia_mayores": groups["mayores_65"] / working * 100,
                "porcentaje_mayores_65": groups["mayores_65"] / groups["total_detalle"].where(groups["total_detalle"].gt(0)) * 100,
            }
        )
        return pd.concat([groups[KEYS], values], axis=1).melt(id_vars=KEYS, var_name="indicador", value_name="valor")

    def _natural_balance(self, vital):
        return vital[KEYS].assign(indicador="saldo_vegetativo", valor=vital["nacimientos"] - vital["defunciones"])
