import pandas as pd
import pyarrow as pa

from src.utils.table_schema import TableSchema
from src.transform.demografia_schema import DATA_STATES

INTEGRATED_INDICATORS = ("gasto_pensiones_pib", "tasa_afiliacion_16_64")
DATE = pd.ArrowDtype(pa.date32())


class KpiIntegradoSchema(TableSchema):
    """KPIs que combinan series de distinta fuente. Guarda numerador y denominador para auditar el cálculo."""

    def __init__(self):
        super().__init__(
            "esquema de KPIs integrados de Oro",
            {
                "anyo": "int64",
                "territorio": "string",
                "indicador": "string",
                "valor": "float64",
                "numerador": "float64",
                "denominador": "float64",
                "unidad": "string",
                "metodologia": "string",
                "fuente": "string",
                "estado_dato": "string",
                "fecha_referencia_numerador": DATE,
                "fecha_referencia_denominador": DATE,
                "valor_publicado": "float64",
                "diferencia_publicado": "float64",
                "run_ids_origen": "string",
                "fecha_generacion": pd.DatetimeTZDtype("us", "UTC"),
            },
            {"valor_publicado", "diferencia_publicado"},
            {"indicador": INTEGRATED_INDICATORS, "estado_dato": DATA_STATES},
        )
