"""Es la única definición del modelo relacional: de aquí salen el DDL de SQLite y el DDL de PostgreSQL generado como script ver docs/08_guia_power_bi.md).
"""

import pandas as pd

TABLES = {
    "dim_tiempo": {"layer": "modelo", "pk": ["tiempo_key"], "fk": {}},
    "dim_territorio": {"layer": "modelo", "pk": ["territorio_key"], "fk": {}},
    "dim_sexo": {"layer": "modelo", "pk": ["sexo_key"], "fk": {}},
    "dim_grupo_edad": {"layer": "modelo", "pk": ["grupo_edad_key"], "fk": {}},
    "dim_fuente": {"layer": "modelo", "pk": ["fuente_key"], "fk": {}},
    "dim_indicador": {"layer": "modelo", "pk": ["indicador_key"], "fk": {}},
    "dim_escenario": {"layer": "escenarios", "pk": ["escenario_key"], "fk": {}},
    "fact_indicadores_anual": {
        "layer": "modelo",
        "pk": ["tiempo_key", "territorio_key", "sexo_key", "grupo_edad_key", "indicador_key"],
        "fk": {
            "tiempo_key": "dim_tiempo",
            "territorio_key": "dim_territorio",
            "sexo_key": "dim_sexo",
            "grupo_edad_key": "dim_grupo_edad",
            "indicador_key": "dim_indicador",
            "fuente_key": "dim_fuente",
        },
    },
    "fact_proyecciones_demograficas": {
        "layer": "escenarios",
        "pk": ["tiempo_key", "territorio_key", "escenario_key", "sexo_key", "grupo_edad_key", "indicador_key"],
        "fk": {
            "tiempo_key": "dim_tiempo",
            "territorio_key": "dim_territorio",
            "escenario_key": "dim_escenario",
            "sexo_key": "dim_sexo",
            "grupo_edad_key": "dim_grupo_edad",
            "indicador_key": "dim_indicador",
            "fuente_key": "dim_fuente",
        },
    },
    "dm_panel_anual": {"layer": "modelo", "pk": ["tiempo_key", "territorio_key"], "fk": {"tiempo_key": "dim_tiempo", "territorio_key": "dim_territorio"}},
    "dm_escenarios_2050": {"layer": "escenarios", "pk": ["anyo", "territorio", "escenario_kr", "grupo_edad", "indicador"], "fk": {}},
    "aux_kpis_integrados": {"layer": "indicadores", "pk": ["anyo", "territorio", "indicador"], "fk": {}},
    "aux_linaje": {"layer": "carga", "pk": ["capa", "dataset"], "fk": {}},
    "aux_calidad_reglas": {"layer": "carga", "pk": ["capa", "run_id", "regla"], "fk": {}},
}

VIEWS = {
    "vw_indicadores_observados": """
SELECT t.anyo, ter.codigo_territorio, ter.nombre_territorio, s.codigo_sexo, s.nombre_sexo, g.codigo_grupo, g.descripcion AS grupo_edad,
       i.codigo_indicador, i.nombre_indicador, i.tipo_indicador, i.codigo_kpi, i.pestana_tablero, i.dominio,
       f.valor, f.unidad, f.estado_dato, fu.organismo AS fuente, f.metodologia, f.dataset_origen
FROM fact_indicadores_anual f
JOIN dim_tiempo t ON t.tiempo_key = f.tiempo_key
JOIN dim_territorio ter ON ter.territorio_key = f.territorio_key
JOIN dim_sexo s ON s.sexo_key = f.sexo_key
JOIN dim_grupo_edad g ON g.grupo_edad_key = f.grupo_edad_key
JOIN dim_indicador i ON i.indicador_key = f.indicador_key
JOIN dim_fuente fu ON fu.fuente_key = f.fuente_key""",
    "vw_kpis_observados": """
SELECT t.anyo, i.codigo_kpi, i.codigo_indicador, i.nombre_indicador, i.pestana_tablero, f.valor, f.unidad, f.estado_dato
FROM fact_indicadores_anual f
JOIN dim_tiempo t ON t.tiempo_key = f.tiempo_key
JOIN dim_indicador i ON i.indicador_key = f.indicador_key
JOIN dim_sexo s ON s.sexo_key = f.sexo_key
JOIN dim_grupo_edad g ON g.grupo_edad_key = f.grupo_edad_key
WHERE i.tipo_indicador = 'kpi' AND s.codigo_sexo = 'total' AND g.codigo_grupo = 'total'""",
    "vw_proyecciones": """
SELECT t.anyo, e.codigo_escenario, e.escenario_kr, e.etiqueta_ine, s.codigo_sexo, g.codigo_grupo, i.codigo_indicador, i.nombre_indicador,
       p.valor, p.unidad, p.estado_dato
FROM fact_proyecciones_demograficas p
JOIN dim_tiempo t ON t.tiempo_key = p.tiempo_key
JOIN dim_escenario e ON e.escenario_key = p.escenario_key
JOIN dim_sexo s ON s.sexo_key = p.sexo_key
JOIN dim_grupo_edad g ON g.grupo_edad_key = p.grupo_edad_key
JOIN dim_indicador i ON i.indicador_key = p.indicador_key""",
}

SQLITE_TYPES = {"int": "INTEGER", "float": "REAL", "bool": "INTEGER", "text": "TEXT", "date": "TEXT", "timestamp": "TEXT"}
POSTGRES_TYPES = {"int": "BIGINT", "float": "DOUBLE PRECISION", "bool": "BOOLEAN", "text": "TEXT", "date": "DATE", "timestamp": "TIMESTAMPTZ"}


def logical_type(dtype):
    text = str(dtype)
    if "date32" in text:
        return "date"
    if isinstance(dtype, pd.DatetimeTZDtype) or text.startswith("datetime64"):
        return "timestamp"
    if text in ("bool", "boolean"):
        return "bool"
    if text.lower().startswith("int"):
        return "int"
    if text.startswith("float"):
        return "float"
    return "text"


def create_table(name, frame, types, schema=None):
    spec = TABLES[name]
    qualified = f"{schema}.{name}" if schema else name
    lines = []
    for column, dtype in frame.dtypes.items():
        not_null = " NOT NULL" if column in spec["pk"] or column in spec["fk"] else ""
        lines.append(f"    {column} {types[logical_type(dtype)]}{not_null}")
    lines.append(f"    PRIMARY KEY ({', '.join(spec['pk'])})")
    for column, target in spec["fk"].items():
        target_table = f"{schema}.{target}" if schema else target
        lines.append(f"    FOREIGN KEY ({column}) REFERENCES {target_table} ({TABLES[target]['pk'][0]})")
    return f"CREATE TABLE {qualified} (\n" + ",\n".join(lines) + "\n);"


def load_order():
    """Dimensiones antes que hechos para respetar las claves foráneas."""
    independent = [name for name, spec in TABLES.items() if not spec["fk"]]
    dependent = [name for name, spec in TABLES.items() if spec["fk"]]
    return independent + dependent
