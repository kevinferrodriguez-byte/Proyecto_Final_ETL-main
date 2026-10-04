# 11. Preparación para Power BI

La capa Oro queda lista para Power BI sin transformaciones complejas: claves enteras, tipos definidos, dimensiones con atributos legibles, una tabla plana de respaldo y vistas desnormalizadas.

## 11.1 Opciones de conexión

| Opción | Cuándo usarla | Pasos |
| --- | --- | --- |
| **A. CSV (recomendada para el curso)** | Power BI Desktop sin controladores adicionales | *Obtener datos → Texto/CSV* (o *Carpeta* sobre `data/serving/csv/`). Los archivos van en UTF-8 con BOM y separador `,`; la configuración regional para decimales debe ser «Inglés (Estados Unidos)» o bien «Usar configuración regional» con punto decimal. |
| **B. Parquet** | Conserva los tipos exactos (fechas, enteros) | *Obtener datos → Parquet* sobre `data/gold/modelo/*.parquet` y `data/gold/escenarios/*.parquet`. |
| **C. PostgreSQL** | Entorno con servidor (recomendado por el profesor) | `psql "$DATABASE_URL" -f data/serving/postgresql/01_ddl.sql` y después `02_carga.sql` (desde la raíz del repositorio). En Power BI, *Obtener datos → PostgreSQL*, esquema `pensiones`. *No verificado contra un servidor (ver [10 §10.5](10_calidad_y_validacion.md#105-lo-que-no-se-pudo-verificar)).* |
| **D. SQLite** | Inspección y SQL ad hoc | `data/serving/pensiones_espana.sqlite` (DB Browser for SQLite o `sqlite3`). Power BI necesita un controlador ODBC de SQLite. |

Para actualizar los datos: `python main.py` y *Actualizar* en Power BI. Las claves son deterministas, así que las relaciones no se rompen.

## 11.2 Tablas que se importan y relaciones

Importe las 14 tablas o, como mínimo, las 11 del modelo y los escenarios. Cree estas relaciones, todas **de uno a varios, con filtro de dirección única desde la dimensión**:

| Dimensión (1) | Columna | Hechos (*) |
| --- | --- | --- |
| `dim_tiempo` | `tiempo_key` | `fact_indicadores_anual`, `fact_proyecciones_demograficas`, `dm_panel_anual` |
| `dim_territorio` | `territorio_key` | `fact_indicadores_anual`, `fact_proyecciones_demograficas`, `dm_panel_anual` |
| `dim_sexo` | `sexo_key` | `fact_indicadores_anual`, `fact_proyecciones_demograficas` |
| `dim_grupo_edad` | `grupo_edad_key` | `fact_indicadores_anual`, `fact_proyecciones_demograficas` |
| `dim_indicador` | `indicador_key` | `fact_indicadores_anual`, `fact_proyecciones_demograficas` |
| `dim_fuente` | `fuente_key` | `fact_indicadores_anual`, `fact_proyecciones_demograficas` |
| `dim_escenario` | `escenario_key` | `fact_proyecciones_demograficas` |

`dm_escenarios_2050`, `aux_kpis_integrados`, `aux_linaje` y `aux_calidad_reglas` son tablas planas **sin relaciones**.

**Buenas prácticas:**

- Use `dim_tiempo[anyo]` como eje. La granularidad es anual, así que **no** marque `dim_tiempo` como tabla de fechas: Power BI exige fechas diarias contiguas.
- Oculte las claves `*_key` en la vista de informe.
- Ordene `nombre_indicador` por `indicador_key`.

## 11.3 Medidas DAX sugeridas

El modelo está en formato largo: cada medida filtra el indicador y, cuando procede, el sexo y el grupo de edad totales.

```DAX
-- Valor observado genérico (respeta los filtros de indicador, sexo y grupo)
Valor observado = SUM ( fact_indicadores_anual[valor] )

-- Medida por KPI (repetir para KPI-01 … KPI-08)
Índice de envejecimiento =
CALCULATE (
    [Valor observado],
    dim_indicador[codigo_indicador] = "indice_envejecimiento",
    dim_sexo[codigo_sexo] = "total",
    dim_grupo_edad[codigo_grupo] = "total"
)

Ratio afiliados por pensión =
CALCULATE ( [Valor observado], dim_indicador[codigo_kpi] = "KPI-07",
            dim_sexo[codigo_sexo] = "total", dim_grupo_edad[codigo_grupo] = "total" )

Gasto pensiones % PIB =
CALCULATE ( [Valor observado], dim_indicador[codigo_kpi] = "KPI-08",
            dim_sexo[codigo_sexo] = "total", dim_grupo_edad[codigo_grupo] = "total" )

-- Proyección oficial (usar con un segmentador de dim_escenario[escenario_kr])
Valor proyectado = SUM ( fact_proyecciones_demograficas[valor] )

-- Serie continua observado + proyectado para gráficos de línea
Valor serie =
IF ( SELECTEDVALUE ( dim_tiempo[es_observado], FALSE () ), [Valor observado], [Valor proyectado] )

-- Variación interanual
Variación interanual =
VAR anyo_actual = MAX ( dim_tiempo[anyo] )
VAR actual = [Valor observado]
VAR anterior = CALCULATE ( [Valor observado], dim_tiempo[anyo] = anyo_actual - 1 )
RETURN IF ( NOT ISBLANK ( anterior ), actual - anterior )

-- Aviso de dato provisional (tarjetas)
Es provisional =
IF ( CALCULATE ( COUNTROWS ( fact_indicadores_anual ),
                 fact_indicadores_anual[estado_dato] = "provisional" ) > 0, "Provisional", "Definitivo" )
```

## 11.4 Estructura sugerida del tablero (KR 2.2)

El campo `dim_indicador[pestana_tablero]` asigna cada indicador a una pestaña:

| Pestaña | Indicadores (`pestana_tablero`) | Visuales sugeridos |
| --- | --- | --- |
| **Demografía** | KPI-01 a KPI-06, % 65+, esperanza de vida al nacer, población | Líneas 1971-2025 con proyección 2026-2076 por escenario; pirámide simplificada (grupo × sexo); saldo vegetativo frente a migratorio (barras) |
| **Cotización y pensiones** | KPI-07, tasa de afiliación, esperanza de vida a los 65, afiliados y pensiones | Ratio afiliados/pensión 2016-2025; afiliación frente a población de 16-64; esperanza de vida a los 65 por sexo |
| **Sostenibilidad financiera** | KPI-08, pensión media, importe de la nómina, PIB y gasto | Gasto/PIB 1995-2024 (marcar los provisionales); pensión media; dispersión dependencia de mayores frente a gasto/PIB desde `dm_panel_anual` |
| **Calidad del dato** (opcional, O1) | `aux_calidad_reglas`, `aux_linaje` | Reglas por capa y resultado; fecha y `run_id` de la última carga |

Para cada visual, añada en la descripción la fuente (`dim_fuente[organismo]`), la unidad y las limitaciones de [12](12_limitaciones_y_proximos_pasos.md): ruptura migratoria de 2021, afiliados **por pensión** y escenarios que son **demográficos, no fiscales**.

## 11.5 Tablero generado (`powerbi/Pensiones_Espana.pbip`)

`python powerbi/generar_tablero.py --validar` genera el tablero desde la capa Oro en formato **PBIP**: un modelo semántico en TMDL y un informe en PBIR, ambos en texto versionable. La opción `--validar` comprueba cada JSON del informe contra los esquemas oficiales de Microsoft.

| Componente | Contenido |
| --- | --- |
| Modelo semántico (`Pensiones_Espana.SemanticModel/`) | 13 tablas cargadas desde `data/serving/csv/` mediante el parámetro `RutaCSV`, más la tabla selectora `sel_indicador_escenario`; 15 relaciones de estrella; 124 medidas DAX en carpetas (KPI, Contexto, Último valor, Contexto KPI, Tarjetas, Índices, Referencias, Títulos, Escenarios INE, Definiciones) |
| 1 · **Resumen ejecutivo** | 3 tarjetas principales (presión demográfica, equilibrio contributivo, esfuerzo financiero) con valor, variación anual, año, fuente y lectura favorable/desfavorable; matriz de los 8 KPIs con tooltip de definición; recuadro «Qué observar» |
| 2 · **Presión demográfica** | Tarjetas KPI-01, KPI-03, KPI-04 y % 65+; área apilada de dependencia juvenil + mayores; estructura por edad al 100 %; fecundidad con umbral de 2,1; saldos vegetativo y migratorio en paneles separados |
| 3 · **Equilibrio contributivo** | Tarjetas KPI-07, afiliados, pensiones y afiliación; afiliados frente a pensiones (índice); ratio; tasa de afiliación; esperanza de vida a los 65 por sexo |
| 4 · **Esfuerzo financiero** | Tarjetas KPI-08, gasto, pensión media y nómina; gasto/PIB; gasto frente a PIB (índice); dispersión dependencia–gasto (asociación); pensión media |
| 5 · **Horizonte 2050** | Selector de indicador; observado (continua) + escenario base (discontinua) + optimista y pesimista (punteadas); valor 2050 en los 8 escenarios; aviso de alcance |
| 6 · **Metodología y calidad** | Recuento de reglas; reglas por capa; advertencias activas; diccionario de indicadores; limitaciones |
| Tooltip (oculta) | Definición, fórmula, unidad, fuente y cobertura del indicador sobre el que se pasa el cursor en la matriz de KPIs |

