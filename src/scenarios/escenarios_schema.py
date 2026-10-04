from src.utils.table_schema import TableSchema
from src.indicators.kpi_schema import KR_SCENARIOS
from src.model.modelo_schema import AGE_GROUP_CODES, TIMESTAMP
from src.transform.demografia_schema import SCENARIOS

PROJECTED_SCENARIOS = tuple(scenario for scenario in SCENARIOS if scenario != "observado")
PROJECTED_KR = tuple(scenario for scenario in KR_SCENARIOS if scenario != "observado")


class DimEscenarioSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de dim_escenario",
            {
                "escenario_key": "int64",
                "codigo_escenario": "string",
                "escenario_kr": "string",
                "etiqueta_ine": "string",
                "descripcion": "string",
                "es_escenario_principal": "bool",
                "fuente_oficial": "string",
                "alcance": "string",
            },
            (),
            {"codigo_escenario": PROJECTED_SCENARIOS, "escenario_kr": PROJECTED_KR},
        )


class FactProyeccionesSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de fact_proyecciones_demograficas",
            {
                "tiempo_key": "int64",
                "territorio_key": "int64",
                "escenario_key": "int64",
                "sexo_key": "int64",
                "grupo_edad_key": "int64",
                "indicador_key": "int64",
                "fuente_key": "int64",
                "valor": "float64",
                "unidad": "string",
                "estado_dato": "string",
                "metodologia": "string",
                "dataset_origen": "string",
                "run_id_origen": "string",
                "gold_run_id": "string",
                "fecha_generacion": TIMESTAMP,
            },
            (),
            {"estado_dato": ("proyectado",)},
        )


class EscenariosMartSchema(TableSchema):
    def __init__(self, indicators, kr_scenarios):
        super().__init__(
            "esquema de dm_escenarios_2050",
            {
                "anyo": "int64",
                "territorio": "string",
                "escenario_kr": "string",
                "escenario": "string",
                "indicador": "string",
                "grupo_edad": "string",
                "valor": "float64",
                "unidad": "string",
                "diferencia_vs_base": "float64",
                "anyo_ultimo_observado": "Int64",
                "valor_ultimo_observado": "float64",
                "variacion_vs_ultimo_observado": "float64",
                "gold_run_id": "string",
            },
            {"anyo_ultimo_observado", "valor_ultimo_observado", "variacion_vs_ultimo_observado"},
            {"escenario_kr": kr_scenarios, "escenario": PROJECTED_SCENARIOS, "indicador": indicators, "grupo_edad": AGE_GROUP_CODES},
        )

