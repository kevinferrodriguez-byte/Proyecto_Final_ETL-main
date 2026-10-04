# Diccionario de datos
Tipos: `int64`/`Int64` entero (Int64 admite nulos), `float64` decimal, `string` texto, `date32` fecha, `timestamp` fecha y hora UTC, `bool` lógico.

## Índice

| Capa | Tabla | Ruta | Grano | Contenido |
| --- | --- | --- | --- | --- |
| Plata | [`stg_poblacion_anual`](#stg_poblacion_anual) | `data/silver/stg_poblacion_anual.parquet` | tabla × consulta × serie × fecha × sexo × edad × escenario | INE: población, eventos, migración, fecundidad y esperanza de vida en formato largo. |
| Plata | [`stg_afiliados_mensual`](#stg_afiliados_mensual) | `data/silver/mercado_laboral_pensiones/stg_afiliados_mensual.parquet` | territorio × año × mes | Afiliados en alta el último día de cada mes (1985-). |
| Plata | [`stg_pensiones_cuantia`](#stg_pensiones_cuantia) | `data/silver/mercado_laboral_pensiones/stg_pensiones_cuantia.parquet` | territorio × tipo de corte × año × mes | Número de pensiones contributivas por clase. |
| Plata | [`stg_pensiones_importe`](#stg_pensiones_importe) | `data/silver/mercado_laboral_pensiones/stg_pensiones_importe.parquet` | territorio × tipo de corte × año × mes | Importe mensual de la nómina de pensiones por clase (miles de euros). |
| Plata | [`stg_macro_anual`](#stg_macro_anual) | `data/silver/macro/stg_macro_anual.parquet` | conjunto × métrica × territorio × año | Eurostat: PIB, gasto en pensiones ESSPROS y población de control. |
| Oro · indicadores | [`kpis_demograficos`](#kpis_demograficos) | `data/gold/indicadores/kpis_demograficos.parquet` | año × territorio × escenario × indicador | KPIs de estructura y saldo vegetativo, observados y proyectados. |
| Oro · indicadores | [`kpi_ratio_sostenibilidad_anual`](#kpi_ratio_sostenibilidad_anual) | `data/gold/indicadores/kpi_ratio_sostenibilidad_anual.parquet` | año × territorio × metodología | Ratio afiliados/pensión, importe y pensión media (diciembre). |
| Oro · indicadores | [`kpis_integrados_anual`](#kpis_integrados_anual) | `data/gold/indicadores/kpis_integrados_anual.parquet` | año × territorio × indicador | KPIs que cruzan fuentes, con numerador y denominador. |
| Oro · modelo | [`dim_tiempo`](#dim_tiempo) | `data/gold/modelo/dim_tiempo.parquet` | una fila por miembro | Dimensión conformada. |
| Oro · modelo | [`dim_territorio`](#dim_territorio) | `data/gold/modelo/dim_territorio.parquet` | una fila por miembro | Dimensión conformada. |
| Oro · modelo | [`dim_sexo`](#dim_sexo) | `data/gold/modelo/dim_sexo.parquet` | una fila por miembro | Dimensión conformada. |
| Oro · modelo | [`dim_grupo_edad`](#dim_grupo_edad) | `data/gold/modelo/dim_grupo_edad.parquet` | una fila por miembro | Dimensión conformada. |
| Oro · modelo | [`dim_fuente`](#dim_fuente) | `data/gold/modelo/dim_fuente.parquet` | una fila por miembro | Dimensión conformada. |
| Oro · modelo | [`dim_indicador`](#dim_indicador) | `data/gold/modelo/dim_indicador.parquet` | una fila por miembro | Dimensión conformada. |
| Oro · modelo | [`fact_indicadores_anual`](#fact_indicadores_anual) | `data/gold/modelo/fact_indicadores_anual.parquet` | año × territorio × sexo × grupo de edad × indicador | Tabla de hechos de datos observados (formato largo). |
| Oro · modelo | [`dm_panel_anual`](#dm_panel_anual) | `data/gold/modelo/dm_panel_anual.parquet` | año × territorio (sexo total) | Conjunto consolidado ancho para Power BI: una columna por indicador. |
| Oro · escenarios | [`dim_escenario`](#dim_escenario) | `data/gold/escenarios/dim_escenario.parquet` | una fila por escenario INE | Escenarios oficiales de las Proyecciones de Población del INE. |
| Oro · escenarios | [`fact_proyecciones_demograficas`](#fact_proyecciones_demograficas) | `data/gold/escenarios/fact_proyecciones_demograficas.parquet` | año × territorio × escenario × sexo × grupo de edad × indicador | Proyecciones demográficas oficiales (sin modelación propia). |
| Oro · escenarios | [`dm_escenarios_2050`](#dm_escenarios_2050) | `data/gold/escenarios/dm_escenarios_2050.parquet` | año × territorio × escenario KR × grupo de edad × indicador | Comparación 2030-2050 de base, optimista y pesimista. |
| Carga | [`aux_linaje`](#aux_linaje) | `data/serving/` | capa × conjunto | Linaje de los conjuntos cargados. |
| Carga | [`aux_calidad_reglas`](#aux_calidad_reglas) | `data/serving/` | capa × ejecución × regla | Reglas de calidad de la última ejecución de cada capa. |

## stg_poblacion_anual

Plata · INE: población, eventos, migración, fecundidad y esperanza de vida en formato largo. Grano: tabla × consulta × serie × fecha × sexo × edad × escenario.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `fuente` | string | No | Organismo que publica el dato (texto) o código de fuente. |
| `tabla_id` | string | No | Identificador de la tabla del INE (API Tempus3). |
| `consulta` | string | No | Consulta de Bronce de la que procede la fila (`detalle` o consulta de control). |
| `run_id` | string | No | Identificador de la ejecución que produjo el artefacto de origen (enlaza con su manifiesto). |
| `codigo_serie` | string | No | Código de la serie publicada por el INE (COD). |
| `fecha_referencia` | date32[day][pyarrow] | No | Fecha a la que se refiere el dato (1 de enero para stocks de población, último día del mes para afiliación, 1 del mes para pensiones, 31/12 para flujos anuales). |
| `anyo` | int64 | No | Año natural. |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `sexo` | string | No | `total`, `hombres` o `mujeres`. |
| `edad_min` | int64 | No | Primera edad incluida. |
| `edad_max` | Int64 | Sí | Última edad incluida; nula en tramos abiertos y totales (nulo estructural). |
| `edad_etiqueta_original` | string | No | Etiqueta de edad publicada por el INE. |
| `tipo_edad` | string | No | `simple`, `tramo_abierto` o `total`. |
| `metrica` | string | No | Variable publicada por la fuente, en `snake_case`. |
| `valor` | float64 | Sí | Valor numérico (nunca imputado: un dato no publicado no tiene fila). |
| `unidad` | string | No | Unidad del valor. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |
| `escenario` | string | No | `observado` o escenario de proyección del INE en `snake_case`. |
| `es_control` | bool | No | True en filas que solo sirven para validar (totales, tramos no vigentes); no se suman. |

## stg_afiliados_mensual

Plata · Afiliados en alta el último día de cada mes (1985-). Grano: territorio × año × mes.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `fuente` | string | No | Organismo que publica el dato (texto) o código de fuente. |
| `archivo_id` | string | No | Archivo de Bronce de la Seguridad Social del que procede la fila. |
| `run_id` | string | No | Identificador de la ejecución que produjo el artefacto de origen (enlaza con su manifiesto). |
| `periodo_original` | string | No | Etiqueta de periodo tal como aparece en la fuente. |
| `fecha_referencia` | date32[day][pyarrow] | No | Fecha a la que se refiere el dato (1 de enero para stocks de población, último día del mes para afiliación, 1 del mes para pensiones, 31/12 para flujos anuales). |
| `anyo` | int64 | No | Año natural. |
| `mes` | int64 | No | Mes (1-12). |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `total_afiliados` | Int64 | Sí | Afiliados en alta laboral (TOTAL SISTEMA) el último día del mes. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |

## stg_pensiones_cuantia

Plata · Número de pensiones contributivas por clase. Grano: territorio × tipo de corte × año × mes.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `fuente` | string | No | Organismo que publica el dato (texto) o código de fuente. |
| `archivo_id` | string | No | Archivo de Bronce de la Seguridad Social del que procede la fila. |
| `run_id` | string | No | Identificador de la ejecución que produjo el artefacto de origen (enlaza con su manifiesto). |
| `periodo_original` | string | No | Etiqueta de periodo tal como aparece en la fuente. |
| `tipo_corte` | string | No | `anual` (dato a diciembre publicado como anual) o `mensual`. |
| `fecha_referencia` | date32[day][pyarrow] | No | Fecha a la que se refiere el dato (1 de enero para stocks de población, último día del mes para afiliación, 1 del mes para pensiones, 31/12 para flujos anuales). |
| `anyo` | int64 | No | Año natural. |
| `mes` | int64 | No | Mes (1-12). |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `pensiones_incapacidad_permanente` | Int64 | Sí | Pensiones de incapacidad permanente. |
| `pensiones_jubilacion` | Int64 | Sí | Pensiones de jubilación. |
| `pensiones_viudedad` | Int64 | Sí | Pensiones de viudedad. |
| `pensiones_orfandad` | Int64 | Sí | Pensiones de orfandad. |
| `pensiones_favor_familiar` | Int64 | Sí | Pensiones en favor de familiares. |
| `total_pensiones` | Int64 | Sí | Pensiones contributivas en vigor el día 1 del mes. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |

## stg_pensiones_importe

Plata · Importe mensual de la nómina de pensiones por clase (miles de euros). Grano: territorio × tipo de corte × año × mes.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `fuente` | string | No | Organismo que publica el dato (texto) o código de fuente. |
| `archivo_id` | string | No | Archivo de Bronce de la Seguridad Social del que procede la fila. |
| `run_id` | string | No | Identificador de la ejecución que produjo el artefacto de origen (enlaza con su manifiesto). |
| `periodo_original` | string | No | Etiqueta de periodo tal como aparece en la fuente. |
| `tipo_corte` | string | No | `anual` (dato a diciembre publicado como anual) o `mensual`. |
| `fecha_referencia` | date32[day][pyarrow] | No | Fecha a la que se refiere el dato (1 de enero para stocks de población, último día del mes para afiliación, 1 del mes para pensiones, 31/12 para flujos anuales). |
| `anyo` | int64 | No | Año natural. |
| `mes` | int64 | No | Mes (1-12). |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `importe_incapacidad_permanente` | float64 | Sí | Importe mensual de las pensiones de incapacidad permanente (miles de euros). |
| `importe_jubilacion` | float64 | Sí | Importe mensual de las pensiones de jubilación (miles de euros). |
| `importe_viudedad` | float64 | Sí | Importe mensual de las pensiones de viudedad (miles de euros). |
| `importe_orfandad` | float64 | Sí | Importe mensual de las pensiones de orfandad (miles de euros). |
| `importe_favor_familiar` | float64 | Sí | Importe mensual de las pensiones en favor de familiares (miles de euros). |
| `importe_total` | float64 | Sí | Importe mensual de la nómina de pensiones contributivas (miles de euros). |
| `unidad` | string | No | Unidad del valor. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |

## stg_macro_anual

Plata · Eurostat: PIB, gasto en pensiones ESSPROS y población de control. Grano: conjunto × métrica × territorio × año.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `fuente` | string | No | Organismo que publica el dato (texto) o código de fuente. |
| `dataset_id` | string | No | Conjunto de Eurostat configurado (`pib`, `gasto_pensiones`, `poblacion_control`). |
| `codigo_eurostat` | string | No | Código del conjunto en la base de datos de Eurostat. |
| `run_id` | string | No | Identificador de la ejecución que produjo el artefacto de origen (enlaza con su manifiesto). |
| `version_fuente` | string | Sí | Marca `updated` publicada por Eurostat (versión de la fuente en la descarga). |
| `metrica` | string | No | Variable publicada por la fuente, en `snake_case`. |
| `anyo` | int64 | No | Año natural. |
| `fecha_referencia` | date32[day][pyarrow] | No | Fecha a la que se refiere el dato (1 de enero para stocks de población, último día del mes para afiliación, 1 del mes para pensiones, 31/12 para flujos anuales). |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `tipo_medida` | string | No | `flujo_anual`, `stock_1_enero` o `ratio_anual`. |
| `unidad` | string | No | Unidad del valor. |
| `unidad_origen` | string | No | Código de unidad de Eurostat. |
| `valor` | float64 | No | Valor numérico (nunca imputado: un dato no publicado no tiene fila). |
| `flag_eurostat` | string | Sí | Flag de estado publicado por Eurostat (`p` provisional, `e` estimado, `b` ruptura); nulo si no hay flag. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |

## kpis_demograficos

Oro · indicadores · KPIs de estructura y saldo vegetativo, observados y proyectados. Grano: año × territorio × escenario × indicador.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `anyo` | int64 | No | Año natural. |
| `fecha_referencia` | date32[day][pyarrow] | No | Fecha a la que se refiere el dato (1 de enero para stocks de población, último día del mes para afiliación, 1 del mes para pensiones, 31/12 para flujos anuales). |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `fuente` | string | No | Organismo que publica el dato (texto) o código de fuente. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |
| `escenario` | string | No | `observado` o escenario de proyección del INE en `snake_case`. |
| `escenario_kr` | string | No | Etiqueta del KR 3.1: `observado`, `base`, `optimista`, `pesimista` o `sensibilidad`. |
| `indicador` | string | No | Código del indicador (ver docs/05_diccionario_metricas.md). |
| `valor` | float64 | Sí | Valor numérico (nunca imputado: un dato no publicado no tiene fila). |
| `unidad` | string | No | Unidad del valor. |
| `silver_run_id` | string | No | run_id de la ejecución de Plata de la que procede el cálculo. |
| `fecha_generacion` | datetime64[us, UTC] | No | Momento (UTC) de la ejecución que generó la fila. |

## kpi_ratio_sostenibilidad_anual

Oro · indicadores · Ratio afiliados/pensión, importe y pensión media (diciembre). Grano: año × territorio × metodología.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `anyo` | int64 | No | Año natural. |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `fuente` | string | No | Organismo que publica el dato (texto) o código de fuente. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |
| `metodologia_ratio` | string | No | Metodología del ratio (`stock_diciembre`: stocks del mes 12). |
| `mes_referencia` | int64 | No | Mes de los stocks usados (12). |
| `fecha_referencia_afiliados` | date32[day][pyarrow] | No | Fecha del numerador (31 de diciembre). |
| `fecha_referencia_pensiones` | date32[day][pyarrow] | No | Fecha del denominador (1 de diciembre). |
| `tipo_corte_pensiones` | string | No | Corte de pensiones usado (se prefiere el anual publicado). |
| `total_afiliados` | int64 | No | Afiliados en alta laboral (TOTAL SISTEMA) el último día del mes. |
| `total_pensiones` | int64 | No | Pensiones contributivas en vigor el día 1 del mes. |
| `ratio_cotizantes_pensionistas` | float64 | Sí | KPI-07: afiliados en alta por pensión contributiva. |
| `importe_nomina_miles_eur` | float64 | Sí | Importe de la nómina de diciembre (miles de euros). |
| `pension_media_eur` | float64 | Sí | Pensión media = importe × 1000 / número de pensiones (EUR/mes). |
| `silver_run_id` | string | No | run_id de la ejecución de Plata de la que procede el cálculo. |
| `fecha_generacion` | datetime64[us, UTC] | No | Momento (UTC) de la ejecución que generó la fila. |

## kpis_integrados_anual

Oro · indicadores · KPIs que cruzan fuentes, con numerador y denominador. Grano: año × territorio × indicador.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `anyo` | int64 | No | Año natural. |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `indicador` | string | No | Código del indicador (ver docs/05_diccionario_metricas.md). |
| `valor` | float64 | No | Valor numérico (nunca imputado: un dato no publicado no tiene fila). |
| `numerador` | float64 | No | Numerador del KPI (conservado para auditar el cálculo). |
| `denominador` | float64 | No | Denominador del KPI. |
| `unidad` | string | No | Unidad del valor. |
| `metodologia` | string | No | Método o serie de origen (por ejemplo `stock_diciembre`, `ine_24309`, `eurostat_nama_10_gdp`). |
| `fuente` | string | No | Organismo que publica el dato (texto) o código de fuente. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |
| `fecha_referencia_numerador` | date32[day][pyarrow] | No | Fecha de referencia del numerador. |
| `fecha_referencia_denominador` | date32[day][pyarrow] | No | Fecha de referencia del denominador. |
| `valor_publicado` | float64 | Sí | Valor que publica la propia fuente para el mismo KPI (control); nulo si no lo publica. |
| `diferencia_publicado` | float64 | Sí | valor − valor_publicado (puntos porcentuales). |
| `run_ids_origen` | string | No | run_id de los conjuntos de Plata usados en numerador y denominador. |
| `fecha_generacion` | datetime64[us, UTC] | No | Momento (UTC) de la ejecución que generó la fila. |

## dim_tiempo

Oro · modelo · Dimensión conformada. Grano: una fila por miembro.

Clave primaria: `(tiempo_key)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `tiempo_key` | int64 | No | Clave de tiempo = año (AAAA). |
| `anyo` | int64 | No | Año natural. |
| `decada` | int64 | No | Primer año de la década. |
| `fecha_inicio` | date32[day][pyarrow] | No | 1 de enero del año. |
| `fecha_fin` | date32[day][pyarrow] | No | 31 de diciembre del año. |
| `es_observado` | bool | No | True si el modelo tiene algún dato observado ese año. |
| `es_proyeccion` | bool | No | True si la capa de escenarios tiene datos proyectados ese año. |

## dim_territorio

Oro · modelo · Dimensión conformada. Grano: una fila por miembro.

Clave primaria: `(territorio_key)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `territorio_key` | int64 | No | Clave de territorio (catálogo modelo.territories). |
| `codigo_territorio` | string | No | Código natural del territorio. |
| `nombre_territorio` | string | No | Nombre del territorio. |
| `nivel_territorial` | string | No | `nacional`, `comunidad_autonoma` o `provincia`. |

## dim_sexo

Oro · modelo · Dimensión conformada. Grano: una fila por miembro.

Clave primaria: `(sexo_key)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `sexo_key` | int64 | No | Clave de sexo (0 total, 1 hombres, 2 mujeres). |
| `codigo_sexo` | string | No | Código natural del sexo. |
| `nombre_sexo` | string | No | Nombre del sexo. |

## dim_grupo_edad

Oro · modelo · Dimensión conformada. Grano: una fila por miembro.

Clave primaria: `(grupo_edad_key)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `grupo_edad_key` | int64 | No | Clave de grupo de edad (0 total, 1 <16, 2 16-64, 3 65+). |
| `codigo_grupo` | string | No | Código natural del grupo de edad. |
| `edad_min` | int64 | No | Primera edad incluida. |
| `edad_max` | Int64 | Sí | Última edad incluida; nula en tramos abiertos y totales (nulo estructural). |
| `descripcion` | string | No | Descripción legible. |

## dim_fuente

Oro · modelo · Dimensión conformada. Grano: una fila por miembro.

Clave primaria: `(fuente_key)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `fuente_key` | int64 | No | Clave de la fuente (catálogo modelo.sources). |
| `codigo_fuente` | string | No | Código natural de la fuente. |
| `organismo` | string | No | Organismo que publica los datos. |
| `acceso` | string | No | Mecanismo de extracción. |
| `url` | string | No | Página oficial de la fuente. |
| `conjuntos` | string | No | Tablas o conjuntos usados. |

## dim_indicador

Oro · modelo · Dimensión conformada. Grano: una fila por miembro.

Clave primaria: `(indicador_key)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `indicador_key` | int64 | No | Clave del indicador (catálogo modelo.indicators). |
| `codigo_indicador` | string | No | Código natural del indicador. |
| `nombre_indicador` | string | No | Nombre legible del indicador. |
| `tipo_indicador` | string | No | `kpi`, `contexto` o `metrica_base`. |
| `codigo_kpi` | string | Sí | KPI-01 … KPI-08 (nulo si no es KPI). |
| `okr` | string | No | Objetivo al que contribuye (O1, O2, O3). |
| `pestana_tablero` | string | No | Pestaña del tablero de Power BI (KR 2.2). |
| `dominio` | string | No | `demografia`, `mercado_laboral`, `pensiones` o `macroeconomia`. |
| `unidad` | string | No | Unidad del valor. |
| `formula` | string | No | Fórmula de cálculo. |
| `codigo_fuente` | string | No | Código natural de la fuente. |
| `origen` | string | No | Conjunto y tabla de origen. |
| `periodicidad` | string | No | Frecuencia del indicador en el modelo. |
| `referencia_temporal` | string | No | Momento del año al que se refiere el dato. |
| `nivel_agregacion` | string | No | Nivel territorial y desagregaciones disponibles. |
| `cobertura_desde` | int64 | No | Primer año observado esperado (base de la completitud del KR 1.2). |
| `cobertura_hasta` | int64 | No | Último año observado esperado. |
| `rango_min` | float64 | No | Mínimo plausible (regla de rangos válidos). |
| `rango_max` | float64 | No | Máximo plausible. |
| `sentido` | string | No | Lectura para el tablero: `mayor_es_mas_riesgo`, `menor_es_mas_riesgo` o `neutro`. |
| `descripcion` | string | No | Descripción legible. |

## fact_indicadores_anual

Oro · modelo · Tabla de hechos de datos observados (formato largo). Grano: año × territorio × sexo × grupo de edad × indicador.

Clave primaria: `(tiempo_key, territorio_key, sexo_key, grupo_edad_key, indicador_key)`. Claves foráneas: `tiempo_key` → `dim_tiempo`, `territorio_key` → `dim_territorio`, `sexo_key` → `dim_sexo`, `grupo_edad_key` → `dim_grupo_edad`, `indicador_key` → `dim_indicador`, `fuente_key` → `dim_fuente`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `tiempo_key` | int64 | No | Clave de tiempo = año (AAAA). |
| `territorio_key` | int64 | No | Clave de territorio (catálogo modelo.territories). |
| `sexo_key` | int64 | No | Clave de sexo (0 total, 1 hombres, 2 mujeres). |
| `grupo_edad_key` | int64 | No | Clave de grupo de edad (0 total, 1 <16, 2 16-64, 3 65+). |
| `indicador_key` | int64 | No | Clave del indicador (catálogo modelo.indicators). |
| `fuente_key` | int64 | No | Clave de la fuente (catálogo modelo.sources). |
| `valor` | float64 | No | Valor numérico (nunca imputado: un dato no publicado no tiene fila). |
| `unidad` | string | No | Unidad del valor. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |
| `metodologia` | string | No | Método o serie de origen (por ejemplo `stock_diciembre`, `ine_24309`, `eurostat_nama_10_gdp`). |
| `dataset_origen` | string | No | Conjunto del que procede la fila (trazabilidad hasta Plata o indicadores). |
| `run_id_origen` | string | No | run_id del conjunto de origen de la fila (Plata o capa de indicadores). |
| `gold_run_id` | string | No | run_id de la ejecución de Oro que escribió la fila. |
| `fecha_generacion` | datetime64[us, UTC] | No | Momento (UTC) de la ejecución que generó la fila. |

## dm_panel_anual

Oro · modelo · Conjunto consolidado ancho para Power BI: una columna por indicador. Grano: año × territorio (sexo total).

Clave primaria: `(tiempo_key, territorio_key)`. Claves foráneas: `tiempo_key` → `dim_tiempo`, `territorio_key` → `dim_territorio`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `tiempo_key` | int64 | No | Clave de tiempo = año (AAAA). |
| `anyo` | int64 | No | Año natural. |
| `territorio_key` | int64 | No | Clave de territorio (catálogo modelo.territories). |
| `poblacion_total` | float64 | Sí | Población residente a 1 de enero. |
| `poblacion_menores_16` | float64 | Sí | Población de 0 a 15 años. |
| `poblacion_16_64` | float64 | Sí | Población de 16 a 64 años (edad de trabajar). |
| `poblacion_65_mas` | float64 | Sí | Población de 65 y más años. |
| `indice_envejecimiento` | float64 | Sí | Índice de envejecimiento (porcentaje). |
| `tasa_dependencia` | float64 | Sí | Tasa de dependencia demográfica (porcentaje). |
| `tasa_dependencia_mayores` | float64 | Sí | Tasa de dependencia de mayores (porcentaje). |
| `indicador_coyuntural_fecundidad` | float64 | Sí | Indicador coyuntural de fecundidad (hijos_por_mujer). |
| `saldo_vegetativo` | float64 | Sí | Saldo vegetativo (personas). |
| `saldo_migratorio_exterior` | float64 | Sí | Saldo migratorio con el extranjero (movimientos_migratorios (hasta 2020) / migraciones (desde 2021)). |
| `ratio_cotizantes_pensionistas` | float64 | Sí | KPI-07: afiliados en alta por pensión contributiva. |
| `gasto_pensiones_pib` | float64 | Sí | Gasto en pensiones sobre el PIB (porcentaje_pib). |
| `porcentaje_mayores_65` | float64 | Sí | Proporción de población de 65 y más años (porcentaje). |
| `esperanza_vida_nacimiento` | float64 | Sí | Esperanza de vida al nacimiento (anos). |
| `esperanza_vida_65` | float64 | Sí | Esperanza de vida a los 65 años (anos). |
| `tasa_afiliacion_16_64` | float64 | Sí | Afiliados por cada 100 personas de 16 a 64 años (porcentaje). |
| `pension_media_mensual` | float64 | Sí | Pensión contributiva media mensual (eur_mes). |
| `nacimientos` | float64 | Sí | Nacimientos (nacimientos). |
| `defunciones` | float64 | Sí | Defunciones (defunciones). |
| `total_afiliados` | float64 | Sí | Afiliados en alta laboral (TOTAL SISTEMA) el último día del mes. |
| `total_pensiones` | float64 | Sí | Pensiones contributivas en vigor el día 1 del mes. |
| `importe_nomina_pensiones` | float64 | Sí | Importe mensual de la nómina de pensiones contributivas (miles_eur). |
| `pib` | float64 | Sí | Producto interior bruto a precios corrientes (millones_eur). |
| `gasto_pensiones` | float64 | Sí | Gasto en pensiones (ESSPROS) (millones_eur). |
| `tiene_datos_provisionales` | bool | No | True si alguna celda del año es provisional. |
| `gold_run_id` | string | No | run_id de la ejecución de Oro que escribió la fila. |

## dim_escenario

Oro · escenarios · Escenarios oficiales de las Proyecciones de Población del INE. Grano: una fila por escenario INE.

Clave primaria: `(escenario_key)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `escenario_key` | int64 | No | Clave del escenario = posición del escenario INE (1 central … 8 saldo migratorio nulo). |
| `codigo_escenario` | string | No | Código natural del escenario INE. |
| `escenario_kr` | string | No | Etiqueta del KR 3.1: `observado`, `base`, `optimista`, `pesimista` o `sensibilidad`. |
| `etiqueta_ine` | string | No | Etiqueta publicada por el INE. |
| `descripcion` | string | No | Descripción legible. |
| `es_escenario_principal` | bool | No | True en base, optimista y pesimista (KR 3.1). |
| `fuente_oficial` | string | No | Publicación oficial de la que procede el escenario. |
| `alcance` | string | No | Qué representa el escenario y qué no (no es un escenario fiscal). |

## fact_proyecciones_demograficas

Oro · escenarios · Proyecciones demográficas oficiales (sin modelación propia). Grano: año × territorio × escenario × sexo × grupo de edad × indicador.

Clave primaria: `(tiempo_key, territorio_key, escenario_key, sexo_key, grupo_edad_key, indicador_key)`. Claves foráneas: `tiempo_key` → `dim_tiempo`, `territorio_key` → `dim_territorio`, `escenario_key` → `dim_escenario`, `sexo_key` → `dim_sexo`, `grupo_edad_key` → `dim_grupo_edad`, `indicador_key` → `dim_indicador`, `fuente_key` → `dim_fuente`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `tiempo_key` | int64 | No | Clave de tiempo = año (AAAA). |
| `territorio_key` | int64 | No | Clave de territorio (catálogo modelo.territories). |
| `escenario_key` | int64 | No | Clave del escenario = posición del escenario INE (1 central … 8 saldo migratorio nulo). |
| `sexo_key` | int64 | No | Clave de sexo (0 total, 1 hombres, 2 mujeres). |
| `grupo_edad_key` | int64 | No | Clave de grupo de edad (0 total, 1 <16, 2 16-64, 3 65+). |
| `indicador_key` | int64 | No | Clave del indicador (catálogo modelo.indicators). |
| `fuente_key` | int64 | No | Clave de la fuente (catálogo modelo.sources). |
| `valor` | float64 | No | Valor numérico (nunca imputado: un dato no publicado no tiene fila). |
| `unidad` | string | No | Unidad del valor. |
| `estado_dato` | string | No | `observado`, `provisional` (flag p/e de Eurostat) o `proyectado` (escenarios del INE). |
| `metodologia` | string | No | Método o serie de origen (por ejemplo `stock_diciembre`, `ine_24309`, `eurostat_nama_10_gdp`). |
| `dataset_origen` | string | No | Conjunto del que procede la fila (trazabilidad hasta Plata o indicadores). |
| `run_id_origen` | string | No | run_id del conjunto de origen de la fila (Plata o capa de indicadores). |
| `gold_run_id` | string | No | run_id de la ejecución de Oro que escribió la fila. |
| `fecha_generacion` | datetime64[us, UTC] | No | Momento (UTC) de la ejecución que generó la fila. |

## dm_escenarios_2050

Oro · escenarios · Comparación 2030-2050 de base, optimista y pesimista. Grano: año × territorio × escenario KR × grupo de edad × indicador.

Clave primaria: `(anyo, territorio, escenario_kr, grupo_edad, indicador)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `anyo` | int64 | No | Año natural. |
| `territorio` | string | No | Código del territorio (`ES` = España). |
| `escenario_kr` | string | No | Etiqueta del KR 3.1: `observado`, `base`, `optimista`, `pesimista` o `sensibilidad`. |
| `escenario` | string | No | `observado` o escenario de proyección del INE en `snake_case`. |
| `indicador` | string | No | Código del indicador (ver docs/05_diccionario_metricas.md). |
| `grupo_edad` | string | No | Código del grupo de edad (`total`, `menores_16`, `activos_16_64`, `mayores_65`). |
| `valor` | float64 | No | Valor numérico (nunca imputado: un dato no publicado no tiene fila). |
| `unidad` | string | No | Unidad del valor. |
| `diferencia_vs_base` | float64 | No | valor − valor del escenario base (mismo año, indicador y grupo). |
| `anyo_ultimo_observado` | Int64 | Sí | Último año observado del indicador en el modelo. |
| `valor_ultimo_observado` | float64 | Sí | Valor observado en ese año (referencia para medir el cambio proyectado). |
| `variacion_vs_ultimo_observado` | float64 | Sí | valor proyectado − último valor observado. |
| `gold_run_id` | string | No | run_id de la ejecución de Oro que escribió la fila. |

## aux_linaje

Carga · clave primaria `(capa, dataset)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `capa` | text | No | Capa o paso del pipeline. |
| `dataset` | text | No | Conjunto publicado. |
| `run_id` | text | No | Identificador de la ejecución que produjo el artefacto de origen (enlaza con su manifiesto). |
| `manifiesto` | text | No | Manifiesto que registra el conjunto. |
| `sha256` | text | No | Huella sha256 verificada del Parquet. |
| `filas` | int | No | Número de filas. |
| `bronze_run_ids` | text | No | Ejecuciones de Bronce de las que procede el conjunto. |

## aux_calidad_reglas

Carga · clave primaria `(capa, run_id, regla)`.

| Columna | Tipo | Nulos | Descripción |
| --- | --- | --- | --- |
| `capa` | text | No | Capa o paso del pipeline. |
| `run_id` | text | No | Identificador de la ejecución que produjo el artefacto de origen (enlaza con su manifiesto). |
| `regla` | text | No | Código de la regla de calidad. |
| `descripcion` | text | No | Descripción legible. |
| `resultado` | text | No | `cumple`, `advertencia`, `falla` o `no_evaluada`. |
| `n_detalles` | int | No | Número de hallazgos de la regla. |
| `detalle` | text | Sí | Hallazgos (truncado a 500 caracteres). |

