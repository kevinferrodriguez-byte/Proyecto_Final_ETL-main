import pandas as pd
import pyarrow as pa

from src.utils.table_schema import TableSchema

SCENARIOS = (
    "observado",
    "central",
    "fecundidad_alta",
    "fecundidad_baja",
    "saldo_migratorio_alto",
    "saldo_migratorio_bajo",
    "fecundidad_y_saldo_migratorio_altos",
    "fecundidad_y_saldo_migratorio_bajos",
    "saldo_migratorio_nulo",
)
DATA_STATES = ("observado", "provisional", "proyectado")


class DemografiaSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema demográfico de Plata",
            {
                "fuente": "string",
                "tabla_id": "string",
                "consulta": "string",
                "run_id": "string",
                "codigo_serie": "string",
                "fecha_referencia": pd.ArrowDtype(pa.date32()),
                "anyo": "int64",
                "territorio": "string",
                "sexo": "string",
                "edad_min": "int64",
                "edad_max": "Int64",
                "edad_etiqueta_original": "string",
                "tipo_edad": "string",
                "metrica": "string",
                "valor": "float64",
                "unidad": "string",
                "estado_dato": "string",
                "escenario": "string",
                "es_control": "bool",
            },
            {"edad_max", "valor"},
            {
                "sexo": ("total", "hombres", "mujeres"),
                "tipo_edad": ("simple", "tramo_abierto", "total"),
                "estado_dato": DATA_STATES,
                "escenario": SCENARIOS,
            },
        )
