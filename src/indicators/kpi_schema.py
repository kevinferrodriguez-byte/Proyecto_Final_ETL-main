import pandas as pd
import pyarrow as pa

from src.utils.table_schema import TableSchema
from src.transform.demografia_schema import DATA_STATES, SCENARIOS

INDICATORS = ("indice_envejecimiento", "tasa_dependencia", "tasa_dependencia_mayores", "porcentaje_mayores_65", "saldo_vegetativo")
KR_SCENARIOS = ("observado", "base", "optimista", "pesimista", "sensibilidad")


class KpiSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de KPIs demográficos de Oro",
            {
                "anyo": "int64",
                "fecha_referencia": pd.ArrowDtype(pa.date32()),
                "territorio": "string",
                "fuente": "string",
                "estado_dato": "string",
                "escenario": "string",
                "escenario_kr": "string",
                "indicador": "string",
                "valor": "float64",
                "unidad": "string",
                "silver_run_id": "string",
                "fecha_generacion": pd.DatetimeTZDtype("us", "UTC"),
            },
            {"valor"},
            {
                "estado_dato": DATA_STATES,
                "escenario": SCENARIOS,
                "escenario_kr": KR_SCENARIOS,
                "indicador": INDICATORS,
                "unidad": ("porcentaje", "personas"),
            },
        )
