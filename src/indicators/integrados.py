from datetime import date

import pandas as pd

from src.indicators.demografia_kpis import DemografiaKpis
from src.indicators.integrados_schema import KpiIntegradoSchema

OBSERVED_STATES = ("observado", "provisional")
KEY = ["anyo", "territorio", "indicador"]


class IndicadoresIntegrados:
    """Calcula los KPIs que relacionan series de distinta fuente.

    - gasto_pensiones_pib = gasto en pensiones ESSPROS / PIB × 100 (ambos de Eurostat, SEC 2010). Se conserva
      el porcentaje que publica Eurostat (valor_publicado) para contrastar el cálculo.
    - tasa_afiliacion_16_64 = afiliados en alta a 31/12 del año t / población de 16-64 años a 1/1 del año t+1 × 100
      (Seguridad Social + INE). Se usa t+1 porque es el stock de población más próximo (un día) a la afiliación.

    No rellena huecos: un año sin numerador o sin denominador no genera fila.
    """

    def __init__(self, config):
        self.integrated = config["indicadores"]["integrados"]
        self.catalog = config["modelo"]["indicators"]
        self.lag = self.integrated["afiliacion_desfase_poblacion_anyos"]
        self.age_classifier = DemografiaKpis(config["indicadores"]["demografia"])
        self.schema = KpiIntegradoSchema()

    def compute(self, macro, afiliados, poblacion, generated_at):
        parts = [
            self.pension_spending(macro["frame"], macro["run_id"]),
            self.affiliation_rate(afiliados["frame"], afiliados["run_id"], poblacion["frame"], poblacion["run_id"]),
        ]
        frame = pd.concat(parts, ignore_index=True)
        frame["fecha_generacion"] = pd.Timestamp(generated_at)
        frame = frame[self.schema.columns()].astype(self.schema.dtypes)
        return frame.sort_values(["indicador", "territorio", "anyo"], ignore_index=True)

    def pension_spending(self, macro, run_id):
        wide = macro.pivot_table(index=["anyo", "territorio"], columns="metrica", values="valor", aggfunc="first")
        states = macro.pivot_table(index=["anyo", "territorio"], columns="metrica", values="estado_dato", aggfunc="first")
        needed = wide[["gasto_pensiones", "pib"]].dropna()
        numerator = needed["gasto_pensiones"]
        denominator = needed["pib"]
        value = numerator / denominator.where(denominator.gt(0)) * 100
        published = wide.get("gasto_pensiones_pib_publicado", pd.Series(dtype="float64")).reindex(needed.index)
        provisional = states.reindex(needed.index)[["gasto_pensiones", "pib"]].eq("provisional").any(axis=1)
        index = needed.index.to_frame(index=False)
        return pd.DataFrame(
            {
                "anyo": index["anyo"].astype("int64"),
                "territorio": index["territorio"],
                "indicador": "gasto_pensiones_pib",
                "valor": value.to_numpy(),
                "numerador": numerator.to_numpy(),
                "denominador": denominator.to_numpy(),
                "unidad": self.catalog["gasto_pensiones_pib"]["unidad"],
                "metodologia": "eurostat_spr_exp_pens_mio_eur / eurostat_nama_10_gdp_cp_meur",
                "fuente": "Eurostat",
                "estado_dato": ["provisional" if flag else "observado" for flag in provisional],
                "fecha_referencia_numerador": [date(int(year), 12, 31) for year in index["anyo"]],
                "fecha_referencia_denominador": [date(int(year), 12, 31) for year in index["anyo"]],
                "valor_publicado": published.to_numpy(),
                "diferencia_publicado": (value - published).to_numpy(),
                "run_ids_origen": run_id,
            }
        )

    def affiliation_rate(self, afiliados, afiliados_run_id, poblacion, poblacion_run_id):
        december = afiliados[afiliados["mes"].eq(12) & afiliados["total_afiliados"].notna()]
        detail = poblacion[
            poblacion["metrica"].eq("poblacion") & poblacion["sexo"].eq("total") & ~poblacion["es_control"] & poblacion["estado_dato"].isin(OBSERVED_STATES)
        ]
        groups = self.age_classifier.age_groups(detail)
        working = groups[["anyo", "territorio", "fecha_referencia", "activos_16_64"]].assign(anyo=lambda frame: frame["anyo"] - self.lag)
        merged = december[["anyo", "territorio", "fecha_referencia", "total_afiliados"]].merge(
            working, on=["anyo", "territorio"], how="inner", suffixes=("_afiliados", "_poblacion"), validate="one_to_one"
        )
        denominator = merged["activos_16_64"].astype("float64")
        numerator = merged["total_afiliados"].astype("float64")
        return pd.DataFrame(
            {
                "anyo": merged["anyo"].astype("int64"),
                "territorio": merged["territorio"],
                "indicador": "tasa_afiliacion_16_64",
                "valor": numerator / denominator.where(denominator.gt(0)) * 100,
                "numerador": numerator,
                "denominador": denominator,
                "unidad": self.catalog["tasa_afiliacion_16_64"]["unidad"],
                "metodologia": f"afiliados_31_dic_t / poblacion_16_64_1_ene_t+{self.lag}",
                "fuente": "Seguridad Social; Instituto Nacional de Estadística",
                "estado_dato": "observado",
                "fecha_referencia_numerador": merged["fecha_referencia_afiliados"],
                "fecha_referencia_denominador": merged["fecha_referencia_poblacion"],
                "valor_publicado": float("nan"),
                "diferencia_publicado": float("nan"),
                "run_ids_origen": f"{afiliados_run_id}; {poblacion_run_id}",
            }
        )
