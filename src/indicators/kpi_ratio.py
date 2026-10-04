import pandas as pd

from src.indicators.kpi_ratio_schema import KpiRatioSchema

KEY = ["territorio", "anyo"]
CUT_PRIORITY = {"anual": 0, "mensual": 1}


class RatioCotizantesPensionistas:
    def __init__(self, kpi_config, source_name):
        self.methodology = kpi_config["methodology"]
        self.month = kpi_config["reference_month"]
        self.source_name = source_name
        self.schema = KpiRatioSchema()

    def compute(self, afiliados, pensiones, silver_run_id, generated_at, importe=None):
        workers = afiliados.loc[afiliados["mes"].eq(self.month), KEY + ["fecha_referencia", "total_afiliados", "estado_dato"]]
        pensions = self._reference_pensions(pensiones)
        if importe is not None:
            amounts = self._reference_pensions(importe, "importe_total")[KEY + ["tipo_corte", "importe_total"]]
            pensions = pensions.merge(amounts, on=KEY + ["tipo_corte"], how="left", validate="one_to_one")
        else:
            pensions = pensions.assign(importe_total=float("nan"))
        merged = workers.merge(pensions, on=KEY, how="outer", suffixes=("_afiliados", "_pensiones"), indicator=True)
        unmatched = {
            "anyos_afiliados_sin_pensiones": sorted(merged.loc[merged["_merge"].eq("left_only"), "anyo"].astype(int).tolist()),
            "anyos_pensiones_sin_afiliados": sorted(merged.loc[merged["_merge"].eq("right_only"), "anyo"].astype(int).tolist()),
        }
        paired = merged[merged["_merge"].eq("both")].reset_index(drop=True)
        mixed = paired["estado_dato_afiliados"].ne(paired["estado_dato_pensiones"])
        if mixed.any():
            raise ValueError(f"El ratio mezclaría estados de dato distintos en los años {sorted(paired.loc[mixed, 'anyo'].tolist())}.")
        denominator = paired["total_pensiones"].astype("float64")
        ratio = paired["total_afiliados"].astype("float64") / denominator.where(denominator.gt(0))
        amount = paired["importe_total"].astype("float64")
        average = amount * 1000 / denominator.where(denominator.gt(0))
        frame = pd.DataFrame(
            {
                "anyo": paired["anyo"],
                "territorio": paired["territorio"],
                "fuente": self.source_name,
                "estado_dato": paired["estado_dato_afiliados"],
                "metodologia_ratio": self.methodology,
                "mes_referencia": self.month,
                "fecha_referencia_afiliados": paired["fecha_referencia_afiliados"],
                "fecha_referencia_pensiones": paired["fecha_referencia_pensiones"],
                "tipo_corte_pensiones": paired["tipo_corte"],
                "total_afiliados": paired["total_afiliados"],
                "total_pensiones": paired["total_pensiones"],
                "ratio_cotizantes_pensionistas": ratio,
                "importe_nomina_miles_eur": amount,
                "pension_media_eur": average,
                "silver_run_id": silver_run_id,
                "fecha_generacion": pd.Timestamp(generated_at),
            }
        )
        frame = frame[self.schema.columns()].astype(self.schema.dtypes).sort_values(KEY, ignore_index=True)
        return {"frame": frame, "unmatched": unmatched}

    def _reference_pensions(self, pensiones, value="total_pensiones"):
        reference = pensiones[pensiones["mes"].eq(self.month)].assign(prioridad=lambda frame: frame["tipo_corte"].map(CUT_PRIORITY))
        reference = reference.sort_values(KEY + ["prioridad"]).drop_duplicates(KEY, keep="first")
        return reference[KEY + ["fecha_referencia", "tipo_corte", value, "estado_dato"]]
