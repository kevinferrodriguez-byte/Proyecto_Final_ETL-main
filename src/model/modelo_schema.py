import pandas as pd
import pyarrow as pa

from src.utils.table_schema import TableSchema
from src.indicators.demografia_kpis import AGE_GROUPS

TOTAL_AGE_GROUP = "total"
AGE_GROUP_CODES = (TOTAL_AGE_GROUP, *AGE_GROUPS)
SEX_CODES = ("total", "hombres", "mujeres")
TERRITORIAL_LEVELS = ("nacional", "comunidad_autonoma", "provincia")
INDICATOR_TYPES = ("kpi", "contexto", "metrica_base")
DOMAINS = ("demografia", "mercado_laboral", "pensiones", "macroeconomia")
OKRS = ("O1", "O2", "O3")
TABS = ("demografia", "cotizacion_pensiones", "sostenibilidad_financiera")
SENSES = ("mayor_es_mas_riesgo", "menor_es_mas_riesgo", "neutro")
OBSERVED_STATES = ("observado", "provisional")
DATE = pd.ArrowDtype(pa.date32())
TIMESTAMP = pd.DatetimeTZDtype("us", "UTC")


class DimTiempoSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de dim_tiempo",
            {
                "tiempo_key": "int64",
                "anyo": "int64",
                "decada": "int64",
                "fecha_inicio": DATE,
                "fecha_fin": DATE,
                "es_observado": "bool",
                "es_proyeccion": "bool",
            },
            (),
            {},
        )


class DimTerritorioSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de dim_territorio",
            {"territorio_key": "int64", "codigo_territorio": "string", "nombre_territorio": "string", "nivel_territorial": "string"},
            (),
            {"nivel_territorial": TERRITORIAL_LEVELS},
        )


class DimSexoSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de dim_sexo",
            {"sexo_key": "int64", "codigo_sexo": "string", "nombre_sexo": "string"},
            (),
            {"codigo_sexo": SEX_CODES},
        )


class DimGrupoEdadSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de dim_grupo_edad",
            {"grupo_edad_key": "int64", "codigo_grupo": "string", "edad_min": "int64", "edad_max": "Int64", "descripcion": "string"},
            {"edad_max"},
            {"codigo_grupo": AGE_GROUP_CODES},
        )


class DimFuenteSchema(TableSchema):
    def __init__(self, codes):
        super().__init__(
            "esquema de dim_fuente",
            {"fuente_key": "int64", "codigo_fuente": "string", "organismo": "string", "acceso": "string", "url": "string", "conjuntos": "string"},
            (),
            {"codigo_fuente": codes},
        )


class DimIndicadorSchema(TableSchema):
    def __init__(self, indicators, sources):
        super().__init__(
            "esquema de dim_indicador",
            {
                "indicador_key": "int64",
                "codigo_indicador": "string",
                "nombre_indicador": "string",
                "tipo_indicador": "string",
                "codigo_kpi": "string",
                "okr": "string",
                "pestana_tablero": "string",
                "dominio": "string",
                "unidad": "string",
                "formula": "string",
                "codigo_fuente": "string",
                "origen": "string",
                "periodicidad": "string",
                "referencia_temporal": "string",
                "nivel_agregacion": "string",
                "cobertura_desde": "int64",
                "cobertura_hasta": "int64",
                "rango_min": "float64",
                "rango_max": "float64",
                "sentido": "string",
                "descripcion": "string",
            },
            {"codigo_kpi"},
            {
                "codigo_indicador": indicators,
                "tipo_indicador": INDICATOR_TYPES,
                "okr": OKRS,
                "pestana_tablero": TABS,
                "dominio": DOMAINS,
                "codigo_fuente": sources,
                "sentido": SENSES,
            },
        )


class FactIndicadoresSchema(TableSchema):
    def __init__(self):
        super().__init__(
            "esquema de fact_indicadores_anual",
            {
                "tiempo_key": "int64",
                "territorio_key": "int64",
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
            {"estado_dato": OBSERVED_STATES},
        )


class PanelSchema(TableSchema):
    """Tabla ancha de consumo directo: una fila por año con los KPIs y sus componentes (sexo total)."""

    def __init__(self, value_columns):
        super().__init__(
            "esquema de dm_panel_anual",
            {
                "tiempo_key": "int64",
                "anyo": "int64",
                "territorio_key": "int64",
                **{column: "float64" for column in value_columns},
                "tiene_datos_provisionales": "bool",
                "gold_run_id": "string",
            },
            set(value_columns),
            {},
        )
