import pandas as pd
import pyarrow as pa

from src.utils.table_schema import TableSchema
from src.transform.demografia_schema import DATA_STATES

MEASURE_TYPES = ("flujo_anual", "stock_1_enero", "ratio_anual")


class MacroSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema macroeconómico de Plata (Eurostat)",
            {
                "fuente": "string",
                "dataset_id": "string",
                "codigo_eurostat": "string",
                "run_id": "string",
                "version_fuente": "string",
                "metrica": "string",
                "anyo": "int64",
                "fecha_referencia": pd.ArrowDtype(pa.date32()),
                "territorio": "string",
                "tipo_medida": "string",
                "unidad": "string",
                "unidad_origen": "string",
                "valor": "float64",
                "flag_eurostat": "string",
                "estado_dato": "string",
            },
            {"flag_eurostat", "version_fuente"},
            {"estado_dato": DATA_STATES, "tipo_medida": MEASURE_TYPES},
        )
