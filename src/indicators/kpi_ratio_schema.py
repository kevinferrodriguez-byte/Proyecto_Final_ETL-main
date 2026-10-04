import pandas as pd
import pyarrow as pa

from src.utils.table_schema import TableSchema
from src.transform.demografia_schema import DATA_STATES
from src.transform.seguridad_social.seguridad_social_schema import CUT_TYPES

METHODOLOGIES = ("stock_diciembre",)


class KpiRatioSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema del ratio cotizantes/pensionistas",
            {
                "anyo": "int64",
                "territorio": "string",
                "fuente": "string",
                "estado_dato": "string",
                "metodologia_ratio": "string",
                "mes_referencia": "int64",
                "fecha_referencia_afiliados": pd.ArrowDtype(pa.date32()),
                "fecha_referencia_pensiones": pd.ArrowDtype(pa.date32()),
                "tipo_corte_pensiones": "string",
                "total_afiliados": "int64",
                "total_pensiones": "int64",
                "ratio_cotizantes_pensionistas": "float64",
                "importe_nomina_miles_eur": "float64",
                "pension_media_eur": "float64",
                "silver_run_id": "string",
                "fecha_generacion": pd.DatetimeTZDtype("us", "UTC"),
            },
            {"ratio_cotizantes_pensionistas", "importe_nomina_miles_eur", "pension_media_eur"},
            {"estado_dato": DATA_STATES, "metodologia_ratio": METHODOLOGIES, "tipo_corte_pensiones": CUT_TYPES},
        )
