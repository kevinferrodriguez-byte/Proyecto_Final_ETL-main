"""Genera la documentación que debe coincidir exactamente con el código y la configuración.

    python -m src.utils.documentacion            # escribe docs/05, docs/06 y docs/09
    python -m src.utils.documentacion --check    # falla si los documentos están desactualizados (lo usa pytest)

- docs/05_diccionario_metricas.md: catálogo de indicadores (modelo.indicators en config/config.yaml).
- docs/06_diccionario_datos.md: todas las tablas y columnas de Plata, indicadores, modelo, escenarios y carga.
- docs/09_catalogo_reglas_calidad.md: todas las reglas de calidad que ejecuta el pipeline, por capa.
"""

from pathlib import Path
import argparse
import sys

import yaml

from src.indicators.integrados_schema import KpiIntegradoSchema
from src.indicators.kpi_ratio_schema import KpiRatioSchema
from src.indicators.kpi_schema import KpiSchema
from src.model.dimensiones import Dimensiones
from src.model.hechos import Hechos
from src.model.panel import Panel
from src.quality import demografia_quality, escenarios_quality, eurostat_quality, integrados_quality, kpi_quality, modelo_quality, seguridad_social_kpi_quality, seguridad_social_quality
from src.scenarios.proyecciones import Proyecciones
from src.serving import carga
from src.serving.esquema_relacional import TABLES
from src.transform.demografia_schema import DemografiaSchema
from src.transform.eurostat.eurostat_schema import MacroSchema
from src.transform.seguridad_social.seguridad_social_schema import AfiliadosSchema, ImporteSchema, PensionesSchema

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
GENERATED_NOTE = "> Documento **generado** por `python -m src.utils.documentacion` a partir de `config/config.yaml` y de los esquemas de `src/`. No lo edite a mano: una prueba (`tests/test_documentacion.py`) falla si se desactualiza."

COLUMNS = {
    # Linaje y metadatos
    "fuente": "Organismo que publica el dato (texto) o código de fuente.",
    "tabla_id": "Identificador de la tabla del INE (API Tempus3).",
    "consulta": "Consulta de Bronce de la que procede la fila (`detalle` o consulta de control).",
    "run_id": "Identificador de la ejecución que produjo el artefacto de origen (enlaza con su manifiesto).",
    "codigo_serie": "Código de la serie publicada por el INE (COD).",
    "archivo_id": "Archivo de Bronce de la Seguridad Social del que procede la fila.",
    "dataset_id": "Conjunto de Eurostat configurado (`pib`, `gasto_pensiones`, `poblacion_control`).",
    "codigo_eurostat": "Código del conjunto en la base de datos de Eurostat.",
    "version_fuente": "Marca `updated` publicada por Eurostat (versión de la fuente en la descarga).",
    "silver_run_id": "run_id de la ejecución de Plata de la que procede el cálculo.",
    "run_id_origen": "run_id del conjunto de origen de la fila (Plata o capa de indicadores).",
    "run_ids_origen": "run_id de los conjuntos de Plata usados en numerador y denominador.",
    "gold_run_id": "run_id de la ejecución de Oro que escribió la fila.",
    "fecha_generacion": "Momento (UTC) de la ejecución que generó la fila.",
    "dataset_origen": "Conjunto del que procede la fila (trazabilidad hasta Plata o indicadores).",
    "metodologia": "Método o serie de origen (por ejemplo `stock_diciembre`, `ine_24309`, `eurostat_nama_10_gdp`).",
    "estado_dato": "`observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE).",
    # Tiempo
    "fecha_referencia": "Fecha a la que se refiere el dato (1 de enero para stocks de población, último día del mes para afiliación, 1 del mes para pensiones, 31/12 para flujos anuales).",
    "anyo": "Año natural.",
    "mes": "Mes (1-12).",
    "periodo_original": "Etiqueta de periodo tal como aparece en la fuente.",
    "tipo_corte": "`anual` (dato a diciembre publicado como anual) o `mensual`.",
    "decada": "Primer año de la década.",
    "fecha_inicio": "1 de enero del año.",
    "fecha_fin": "31 de diciembre del año.",
    "es_observado": "True si el modelo tiene algún dato observado ese año.",
    "es_proyeccion": "True si la capa de escenarios tiene datos proyectados ese año.",
    # Dimensiones de negocio
    "territorio": "Código del territorio (`ES` = España).",
    "sexo": "`total`, `hombres` o `mujeres`.",
    "edad_min": "Primera edad incluida.",
    "edad_max": "Última edad incluida; nula en tramos abiertos y totales (nulo estructural).",
    "edad_etiqueta_original": "Etiqueta de edad publicada por el INE.",
    "tipo_edad": "`simple`, `tramo_abierto` o `total`.",
    "es_control": "True en filas que solo sirven para validar (totales, tramos no vigentes); no se suman.",
    "metrica": "Variable publicada por la fuente, en `snake_case`.",
    "valor": "Valor numérico (nunca imputado: un dato no publicado no tiene fila).",
    "unidad": "Unidad del valor.",
    "unidad_origen": "Código de unidad de Eurostat.",
    "flag_eurostat": "Flag de estado publicado por Eurostat (`p` provisional, `e` estimado, `b` ruptura); nulo si no hay flag.",
    "tipo_medida": "`flujo_anual`, `stock_1_enero` o `ratio_anual`.",
    "escenario": "`observado` o escenario de proyección del INE en `snake_case`.",
    "escenario_kr": "Etiqueta del KR 3.1: `observado`, `base`, `optimista`, `pesimista` o `sensibilidad`.",
    "indicador": "Código del indicador (ver docs/05_diccionario_metricas.md).",
    "grupo_edad": "Código del grupo de edad (`total`, `menores_16`, `activos_16_64`, `mayores_65`).",
    # Seguridad Social
    "total_afiliados": "Afiliados en alta laboral (TOTAL SISTEMA) el último día del mes.",
    "total_pensiones": "Pensiones contributivas en vigor el día 1 del mes.",
    "pensiones_incapacidad_permanente": "Pensiones de incapacidad permanente.",
    "pensiones_jubilacion": "Pensiones de jubilación.",
    "pensiones_viudedad": "Pensiones de viudedad.",
    "pensiones_orfandad": "Pensiones de orfandad.",
    "pensiones_favor_familiar": "Pensiones en favor de familiares.",
    "importe_total": "Importe mensual de la nómina de pensiones contributivas (miles de euros).",
    "importe_incapacidad_permanente": "Importe mensual de las pensiones de incapacidad permanente (miles de euros).",
    "importe_jubilacion": "Importe mensual de las pensiones de jubilación (miles de euros).",
    "importe_viudedad": "Importe mensual de las pensiones de viudedad (miles de euros).",
    "importe_orfandad": "Importe mensual de las pensiones de orfandad (miles de euros).",
    "importe_favor_familiar": "Importe mensual de las pensiones en favor de familiares (miles de euros).",
    "metodologia_ratio": "Metodología del ratio (`stock_diciembre`: stocks del mes 12).",
    "mes_referencia": "Mes de los stocks usados (12).",
    "fecha_referencia_afiliados": "Fecha del numerador (31 de diciembre).",
    "fecha_referencia_pensiones": "Fecha del denominador (1 de diciembre).",
    "tipo_corte_pensiones": "Corte de pensiones usado (se prefiere el anual publicado).",
    "ratio_cotizantes_pensionistas": "KPI-07: afiliados en alta por pensión contributiva.",
    "importe_nomina_miles_eur": "Importe de la nómina de diciembre (miles de euros).",
    "pension_media_eur": "Pensión media = importe × 1000 / número de pensiones (EUR/mes).",
    # KPIs integrados
    "numerador": "Numerador del KPI (conservado para auditar el cálculo).",
    "denominador": "Denominador del KPI.",
    "fecha_referencia_numerador": "Fecha de referencia del numerador.",
    "fecha_referencia_denominador": "Fecha de referencia del denominador.",
    "valor_publicado": "Valor que publica la propia fuente para el mismo KPI (control); nulo si no lo publica.",
    "diferencia_publicado": "valor − valor_publicado (puntos porcentuales).",
    # Claves y dimensiones
    "tiempo_key": "Clave de tiempo = año (AAAA).",
    "territorio_key": "Clave de territorio (catálogo modelo.territories).",
    "sexo_key": "Clave de sexo (0 total, 1 hombres, 2 mujeres).",
    "grupo_edad_key": "Clave de grupo de edad (0 total, 1 <16, 2 16-64, 3 65+).",
    "indicador_key": "Clave del indicador (catálogo modelo.indicators).",
    "fuente_key": "Clave de la fuente (catálogo modelo.sources).",
    "escenario_key": "Clave del escenario = posición del escenario INE (1 central … 8 saldo migratorio nulo).",
    "codigo_territorio": "Código natural del territorio.",
    "nombre_territorio": "Nombre del territorio.",
    "nivel_territorial": "`nacional`, `comunidad_autonoma` o `provincia`.",
    "codigo_sexo": "Código natural del sexo.",
    "nombre_sexo": "Nombre del sexo.",
    "codigo_grupo": "Código natural del grupo de edad.",
    "descripcion": "Descripción legible.",
    "codigo_fuente": "Código natural de la fuente.",
    "organismo": "Organismo que publica los datos.",
    "acceso": "Mecanismo de extracción.",
    "url": "Página oficial de la fuente.",
    "conjuntos": "Tablas o conjuntos usados.",
    "codigo_indicador": "Código natural del indicador.",
    "nombre_indicador": "Nombre legible del indicador.",
    "tipo_indicador": "`kpi`, `contexto` o `metrica_base`.",
    "codigo_kpi": "KPI-01 … KPI-08 (nulo si no es KPI).",
    "okr": "Objetivo al que contribuye (O1, O2, O3).",
    "pestana_tablero": "Pestaña del tablero de Power BI (KR 2.2).",
    "dominio": "`demografia`, `mercado_laboral`, `pensiones` o `macroeconomia`.",
    "formula": "Fórmula de cálculo.",
    "origen": "Conjunto y tabla de origen.",
    "periodicidad": "Frecuencia del indicador en el modelo.",
    "referencia_temporal": "Momento del año al que se refiere el dato.",
    "nivel_agregacion": "Nivel territorial y desagregaciones disponibles.",
    "cobertura_desde": "Primer año observado esperado (base de la completitud del KR 1.2).",
    "cobertura_hasta": "Último año observado esperado.",
    "rango_min": "Mínimo plausible (regla de rangos válidos).",
    "rango_max": "Máximo plausible.",
    "sentido": "Lectura para el tablero: `mayor_es_mas_riesgo`, `menor_es_mas_riesgo` o `neutro`.",
    "codigo_escenario": "Código natural del escenario INE.",
    "etiqueta_ine": "Etiqueta publicada por el INE.",
    "es_escenario_principal": "True en base, optimista y pesimista (KR 3.1).",
    "fuente_oficial": "Publicación oficial de la que procede el escenario.",
    "alcance": "Qué representa el escenario y qué no (no es un escenario fiscal).",
    "diferencia_vs_base": "valor − valor del escenario base (mismo año, indicador y grupo).",
    "anyo_ultimo_observado": "Último año observado del indicador en el modelo.",
    "valor_ultimo_observado": "Valor observado en ese año (referencia para medir el cambio proyectado).",
    "variacion_vs_ultimo_observado": "valor proyectado − último valor observado.",
    "tiene_datos_provisionales": "True si alguna celda del año es provisional.",
    "poblacion_total": "Población residente a 1 de enero.",
    "poblacion_menores_16": "Población de 0 a 15 años.",
    "poblacion_16_64": "Población de 16 a 64 años (edad de trabajar).",
    "poblacion_65_mas": "Población de 65 y más años.",
    # Carga
    "capa": "Capa o paso del pipeline.",
    "dataset": "Conjunto publicado.",
    "manifiesto": "Manifiesto que registra el conjunto.",
    "sha256": "Huella sha256 verificada del Parquet.",
    "filas": "Número de filas.",
    "bronze_run_ids": "Ejecuciones de Bronce de las que procede el conjunto.",
    "regla": "Código de la regla de calidad.",
    "resultado": "`cumple`, `advertencia`, `falla` o `no_evaluada`.",
    "n_detalles": "Número de hallazgos de la regla.",
    "detalle": "Hallazgos (truncado a 500 caracteres).",
}

AUX_COLUMNS = {
    "aux_linaje": {"capa": "text", "dataset": "text", "run_id": "text", "manifiesto": "text", "sha256": "text", "filas": "int", "bronze_run_ids": "text"},
    "aux_calidad_reglas": {"capa": "text", "run_id": "text", "regla": "text", "descripcion": "text", "resultado": "text", "n_detalles": "int", "detalle": "text"},
}


def load_config():
    with (ROOT / "config" / "config.yaml").open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def registry(config):
    dimensions = Dimensiones(config).schemas
    scenarios = Proyecciones(config).schemas
    return [
        ("Plata", "stg_poblacion_anual", "data/silver/", DemografiaSchema(), "tabla × consulta × serie × fecha × sexo × edad × escenario", "INE: población, eventos, migración, fecundidad y esperanza de vida en formato largo."),
        ("Plata", "stg_afiliados_mensual", "data/silver/mercado_laboral_pensiones/", AfiliadosSchema(), "territorio × año × mes", "Afiliados en alta el último día de cada mes (1985-)."),
        ("Plata", "stg_pensiones_cuantia", "data/silver/mercado_laboral_pensiones/", PensionesSchema(), "territorio × tipo de corte × año × mes", "Número de pensiones contributivas por clase."),
        ("Plata", "stg_pensiones_importe", "data/silver/mercado_laboral_pensiones/", ImporteSchema(), "territorio × tipo de corte × año × mes", "Importe mensual de la nómina de pensiones por clase (miles de euros)."),
        ("Plata", "stg_macro_anual", "data/silver/macro/", MacroSchema(), "conjunto × métrica × territorio × año", "Eurostat: PIB, gasto en pensiones ESSPROS y población de control."),
        ("Oro · indicadores", "kpis_demograficos", "data/gold/indicadores/", KpiSchema(), "año × territorio × escenario × indicador", "KPIs de estructura y saldo vegetativo, observados y proyectados."),
        ("Oro · indicadores", "kpi_ratio_sostenibilidad_anual", "data/gold/indicadores/", KpiRatioSchema(), "año × territorio × metodología", "Ratio afiliados/pensión, importe y pensión media (diciembre)."),
        ("Oro · indicadores", "kpis_integrados_anual", "data/gold/indicadores/", KpiIntegradoSchema(), "año × territorio × indicador", "KPIs que cruzan fuentes, con numerador y denominador."),
        *[("Oro · modelo", name, "data/gold/modelo/", schema, "una fila por miembro", "Dimensión conformada.") for name, schema in dimensions.items()],
        ("Oro · modelo", "fact_indicadores_anual", "data/gold/modelo/", Hechos(config).schema, "año × territorio × sexo × grupo de edad × indicador", "Tabla de hechos de datos observados (formato largo)."),
        ("Oro · modelo", "dm_panel_anual", "data/gold/modelo/", Panel(config).schema, "año × territorio (sexo total)", "Conjunto consolidado ancho para Power BI: una columna por indicador."),
        *[("Oro · escenarios", name, "data/gold/escenarios/", schema, grain, text) for (name, schema), (grain, text) in zip(scenarios.items(), [
            ("una fila por escenario INE", "Escenarios oficiales de las Proyecciones de Población del INE."),
            ("año × territorio × escenario × sexo × grupo de edad × indicador", "Proyecciones demográficas oficiales (sin modelación propia)."),
            ("año × territorio × escenario KR × grupo de edad × indicador", "Comparación 2030-2050 de base, optimista y pesimista."),
        ])],
    ]


def data_dictionary(config):
    catalog = config["modelo"]["indicators"]
    lines = ["# Diccionario de datos", "", GENERATED_NOTE, "", "Tipos: `int64`/`Int64` entero (Int64 admite nulos), `float64` decimal, `string` texto, `date32` fecha, `timestamp` fecha y hora UTC, `bool` lógico.", ""]
    lines += ["## Índice", "", "| Capa | Tabla | Ruta | Grano | Contenido |", "| --- | --- | --- | --- | --- |"]
    tables = registry(config)
    for layer, name, path, _, grain, text in tables:
        lines.append(f"| {layer} | [`{name}`](#{name}) | `{path}{name}.parquet` | {grain} | {text} |")
    lines += ["| Carga | [`aux_linaje`](#aux_linaje) | `data/serving/` | capa × conjunto | Linaje de los conjuntos cargados. |", "| Carga | [`aux_calidad_reglas`](#aux_calidad_reglas) | `data/serving/` | capa × ejecución × regla | Reglas de calidad de la última ejecución de cada capa. |", ""]
    for layer, name, _, schema, grain, text in tables:
        spec = TABLES.get(name, {})
        lines += [f"## {name}", "", f"{layer} · {text} Grano: {grain}.", ""]
        if spec:
            lines.append(f"Clave primaria: `({', '.join(spec['pk'])})`." + (" Claves foráneas: " + ", ".join(f"`{column}` → `{target}`" for column, target in spec["fk"].items()) + "." if spec["fk"] else ""))
            lines.append("")
        lines += ["| Columna | Tipo | Nulos | Descripción |", "| --- | --- | --- | --- |"]
        for column, dtype in schema.dtypes.items():
            description = COLUMNS.get(column) or (f"{catalog[column]['nombre']} ({catalog[column]['unidad']})." if column in catalog else None)
            if description is None:
                raise KeyError(f"La columna {name}.{column} no tiene descripción en src/utils/documentacion.py (COLUMNS).")
            lines.append(f"| `{column}` | {dtype} | {'Sí' if column in schema.nullable else 'No'} | {description} |")
        lines.append("")
    for name, columns in AUX_COLUMNS.items():
        spec = TABLES[name]
        lines += [f"## {name}", "", f"Carga · clave primaria `({', '.join(spec['pk'])})`.", "", "| Columna | Tipo | Nulos | Descripción |", "| --- | --- | --- | --- |"]
        lines += [f"| `{column}` | {kind} | {'Sí' if column == 'detalle' else 'No'} | {COLUMNS[column]} |" for column, kind in columns.items()]
        lines.append("")
    return "\n".join(lines)


def metrics_dictionary(config):
    catalog = config["modelo"]["indicators"]
    sources = config["modelo"]["sources"]
    lines = [
        "# Diccionario de métricas",
        "",
        GENERATED_NOTE,
        "",
        "Responde a la prioridad 2 de la retroalimentación: cada métrica con fórmula, frecuencia, unidad, fuente y nivel de agregación. Es la misma información que la tabla `dim_indicador` del modelo, de modo que Power BI y la documentación no pueden divergir.",
        "",
        "## Resumen",
        "",
        "| Código | Indicador | Tipo | Fórmula | Frecuencia | Unidad | Fuente | Nivel de agregación | Cobertura observada | Tabla Oro |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    ordered = sorted(catalog.items(), key=lambda item: item[1]["key"])
    for code, spec in ordered:
        levels = ", ".join(spec["desagregaciones"])
        lines.append(
            f"| {spec.get('codigo_kpi', '—')} | `{code}` · {spec['nombre']} | {spec['tipo']} | {spec['formula']} | anual ({spec['referencia_temporal']}) | {spec['unidad']} | {sources[spec['fuente']]['organismo']} | nacional; {levels} | {spec['cobertura']['desde']}–{spec['cobertura']['hasta']} | `fact_indicadores_anual`, `dm_panel_anual` |"
        )
    lines += ["", "## Ficha de cada indicador", ""]
    for code, spec in ordered:
        lines += [
            f"### {spec.get('codigo_kpi', spec['tipo'])} · {spec['nombre']} (`{code}`)",
            "",
            spec["descripcion"],
            "",
            f"- **Fórmula:** {spec['formula']}",
            f"- **Unidad:** {spec['unidad']} · **Frecuencia:** anual · **Referencia temporal:** {spec['referencia_temporal']}",
            f"- **Fuente:** {sources[spec['fuente']]['organismo']} · **Origen en el pipeline:** `{spec['origen']}`",
            f"- **Desagregaciones:** {', '.join(spec['desagregaciones'])} · **Cobertura observada esperada:** {spec['cobertura']['desde']}–{spec['cobertura']['hasta']}",
            f"- **Rango válido:** [{spec['rango']['min']}, {spec['rango']['max']}] · **Lectura:** {spec['sentido']} · **OKR:** {spec['okr']} · **Pestaña del tablero:** {spec['pestana']}",
            "",
        ]
    return "\n".join(lines)


def quality_catalog():
    layers = [
        ("Plata INE", "stg_poblacion_anual", demografia_quality.RULES),
        ("Plata Seguridad Social · afiliados", "stg_afiliados_mensual", seguridad_social_quality.AFILIADOS_RULES),
        ("Plata Seguridad Social · pensiones", "stg_pensiones_cuantia", seguridad_social_quality.PENSIONES_RULES),
        ("Plata Seguridad Social · importe", "stg_pensiones_importe", seguridad_social_quality.IMPORTE_RULES),
        ("Plata Eurostat", "stg_macro_anual", eurostat_quality.RULES),
        ("Oro · indicadores demográficos", "kpis_demograficos", kpi_quality.RULES),
        ("Oro · indicadores de pensiones", "kpi_ratio_sostenibilidad_anual", seguridad_social_kpi_quality.RULES),
        ("Oro · indicadores integrados", "kpis_integrados_anual", (*integrados_quality.RULES, integrados_quality.PUBLISHED_RULE)),
        ("Oro · modelo", "modelo dimensional", (*modelo_quality.RULES, *modelo_quality.WARNINGS)),
        ("Oro · escenarios", "capa de escenarios", escenarios_quality.RULES),
        ("Carga", "SQLite y CSV", carga.RULES),
    ]
    lines = [
        "# Catálogo de reglas de calidad",
        "",
        GENERATED_NOTE,
        "",
        "Además de estas reglas, cada capa comprueba el esquema (`QLT-001`: columnas, tipos, nulos obligatorios y dominios) antes de evaluar el resto y la integridad de Bronce (sha256 y tamaño de cada payload frente a su manifiesto) antes de promover datos a Plata. Una regla en `falla` detiene la escritura de la capa; las marcadas como advertencia (atípicos, consistencia entre fuentes) se registran sin detener el pipeline.",
        "",
    ]
    total = 0
    for layer, dataset, rules in layers:
        lines += [f"## {layer} (`{dataset}`)", "", "| Regla | Criterio |", "| --- | --- |"]
        lines += [f"| `{name}` | {description} |" for name, description in rules]
        lines.append("")
        total += len(rules)
    lines.append(f"Total: {total} reglas específicas (más la comprobación de esquema de cada conjunto).")
    return "\n".join(lines) + "\n"


def documents(config):
    return {
        DOCS / "05_diccionario_metricas.md": metrics_dictionary(config) + "\n",
        DOCS / "06_diccionario_datos.md": data_dictionary(config) + "\n",
        DOCS / "09_catalogo_reglas_calidad.md": quality_catalog(),
    }


def main():
    parser = argparse.ArgumentParser(description="Genera los documentos sincronizados con el código.")
    parser.add_argument("--check", action="store_true", help="Solo comprueba que están actualizados.")
    arguments = parser.parse_args()
    stale = []
    for path, content in documents(load_config()).items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(path.name)
            if not arguments.check:
                path.write_text(content, encoding="utf-8")
    if arguments.check and stale:
        print(f"Documentos desactualizados: {', '.join(stale)}. Ejecute python -m src.utils.documentacion.", file=sys.stderr)
        return 1
    print("Documentos actualizados: " + (", ".join(stale) if stale else "ninguno (ya estaban al día)"))
    return 0



if __name__ == "__main__":
    sys.exit(main())
