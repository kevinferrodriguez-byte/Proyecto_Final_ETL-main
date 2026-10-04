from datetime import date

import pandas as pd

from src.transform.eurostat.eurostat_schema import MacroSchema

TIME_DIMENSION = "time"
GEO_DIMENSION = "geo"
REFERENCE_DATES = {"stock_1_enero": (1, 1), "flujo_anual": (12, 31), "ratio_anual": (12, 31)}


class EurostatNormalizer:
    """Pasa la tabla larga de JSON-stat al esquema de Plata con mapeos estrictos declarados en la configuración.

    - Toda dimensión que no sea tiempo, territorio o la dimensión de métrica debe tener un único valor
      (el filtro de la consulta); si no, el conjunto no es el esperado y se rechaza.
    - Cada flag de Eurostat debe tener un estado de dato documentado (`status_flags`).
    """

    def __init__(self, source_config):
        self.source_name = source_config["name"]
        self.datasets = source_config["datasets"]
        self.territories = source_config["territories"]
        self.status_flags = source_config["status_flags"]
        self.schema = MacroSchema()

    def normalize(self, payload, frame):
        dataset_id = payload["dataset_id"]
        dataset = self.datasets[dataset_id]
        metric_dimension = dataset["metrics"]["dimension"]
        metric_values = dataset["metrics"]["values"]
        for column in (TIME_DIMENSION, GEO_DIMENSION, metric_dimension):
            if column not in frame.columns:
                raise ValueError(f"El conjunto Eurostat {dataset_id} no tiene la dimensión {column}.")
        fixed = [column for column in frame.columns if column not in (TIME_DIMENSION, GEO_DIMENSION, metric_dimension, "valor", "flag")]
        varying = [column for column in fixed if frame[column].nunique() > 1]
        if varying:
            raise ValueError(f"El conjunto Eurostat {dataset_id} trae varias categorías en {varying}; revise sources.eurostat.datasets.{dataset_id}.filters.")
        unknown_metrics = sorted(set(frame[metric_dimension]) - set(metric_values))
        if unknown_metrics:
            raise ValueError(f"El conjunto Eurostat {dataset_id} trae valores de {metric_dimension} sin mapeo: {unknown_metrics}.")
        unknown_geo = sorted(set(frame[GEO_DIMENSION]) - set(self.territories))
        if unknown_geo:
            raise ValueError(f"El conjunto Eurostat {dataset_id} trae territorios sin mapeo en sources.eurostat.territories: {unknown_geo}.")
        flags = frame["flag"].dropna()
        unknown_flags = sorted(set(flags) - set(self.status_flags))
        if unknown_flags:
            raise ValueError(f"El conjunto Eurostat {dataset_id} trae flags sin estado documentado en sources.eurostat.status_flags: {unknown_flags}.")
        if frame["valor"].isna().any():
            raise ValueError(f"El conjunto Eurostat {dataset_id} trae observaciones sin valor.")

        years = pd.to_numeric(frame[TIME_DIMENSION], errors="raise").astype("int64")
        specs = frame[metric_dimension].map(metric_values)
        measure = specs.map(lambda spec: spec["tipo_medida"])
        reference = [date(int(year), *REFERENCE_DATES[kind]) for year, kind in zip(years, measure)]
        result = pd.DataFrame(
            {
                "fuente": self.source_name,
                "dataset_id": dataset_id,
                "codigo_eurostat": dataset["code"],
                "run_id": payload["run_id"],
                "version_fuente": payload.get("source_updated"),
                "metrica": specs.map(lambda spec: spec["metrica"]),
                "anyo": years,
                "fecha_referencia": reference,
                "territorio": frame[GEO_DIMENSION].map(self.territories),
                "tipo_medida": measure,
                "unidad": specs.map(lambda spec: spec["unidad"]),
                "unidad_origen": frame[metric_dimension],
                "valor": pd.to_numeric(frame["valor"], errors="raise").astype("float64"),
                "flag_eurostat": frame["flag"],
                "estado_dato": frame["flag"].map(self.status_flags).fillna("observado"),
            }
        )
        return result[self.schema.columns()].astype(self.schema.dtypes)
