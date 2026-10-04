import pandas as pd
import pyarrow as pa

from src.utils.table_schema import TableSchema
from src.transform.demografia_schema import DATA_STATES

CUT_TYPES = ("anual", "mensual")
PENSION_CLASSES = (
    "pensiones_incapacidad_permanente",
    "pensiones_jubilacion",
    "pensiones_viudedad",
    "pensiones_orfandad",
    "pensiones_favor_familiar",
)
LINEAGE_DTYPES = {"fuente": "string", "archivo_id": "string", "run_id": "string"}


class AfiliadosSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de afiliados de Plata",
            {
                **LINEAGE_DTYPES,
                "periodo_original": "string",
                "fecha_referencia": pd.ArrowDtype(pa.date32()),
                "anyo": "int64",
                "mes": "int64",
                "territorio": "string",
                "total_afiliados": "Int64",
                "estado_dato": "string",
            },
            {"total_afiliados"},
            {"estado_dato": DATA_STATES},
        )


class PensionesSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de pensiones de Plata",
            {
                **LINEAGE_DTYPES,
                "periodo_original": "string",
                "tipo_corte": "string",
                "fecha_referencia": pd.ArrowDtype(pa.date32()),
                "anyo": "int64",
                "mes": "int64",
                "territorio": "string",
                **{name: "Int64" for name in PENSION_CLASSES},
                "total_pensiones": "Int64",
                "estado_dato": "string",
            },
            set(PENSION_CLASSES) | {"total_pensiones"},
            {"tipo_corte": CUT_TYPES, "estado_dato": DATA_STATES},
        )


IMPORTE_CLASSES = tuple(name.replace("pensiones_", "importe_", 1) for name in PENSION_CLASSES)


class ImporteSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de importe de la nómina de pensiones de Plata",
            {
                **LINEAGE_DTYPES,
                "periodo_original": "string",
                "tipo_corte": "string",
                "fecha_referencia": pd.ArrowDtype(pa.date32()),
                "anyo": "int64",
                "mes": "int64",
                "territorio": "string",
                **{name: "float64" for name in IMPORTE_CLASSES},
                "importe_total": "float64",
                "unidad": "string",
                "estado_dato": "string",
            },
            set(IMPORTE_CLASSES) | {"importe_total"},
            {"tipo_corte": CUT_TYPES, "estado_dato": DATA_STATES, "unidad": ("miles_eur",)},
        )
