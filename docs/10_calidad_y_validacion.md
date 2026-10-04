# 10. Estrategia de calidad y validación (Fase 4)

## 10.1 Estrategia

La calidad se aplica en cada capa, antes de escribir:

- `QualityEvaluation` registra cada regla con su resultado (`cumple`, `advertencia`, `falla`, `no_evaluada`) y sus hallazgos.
- `QualityReport` escribe `{run_id}.quality.json` junto al manifiesto, también cuando la capa se rechaza.
- Una `falla` impide escribir Parquet y manifiesto, de modo que la capa siguiente sigue leyendo la última versión aprobada.

El catálogo completo, con 111 reglas específicas más la validación de esquema de cada conjunto, se genera desde el código en [09_catalogo_reglas_calidad.md](09_catalogo_reglas_calidad.md).

| Control exigido | Cómo se implementa | Reglas (ejemplos) |
| --- | --- | --- |
| **Tipos de datos** | Un `TableSchema` por conjunto: columnas exactas (ni faltantes ni sobrantes), dtype exacto, nulos permitidos y dominios. Se valida en cada capa y otra vez en la entrada de la siguiente. | `QLT-001 esquema`, `entradas_esquema`, `MOD-01`, `MOD-06`, `ESC-03` |
| **Valores nulos** | Fracción de nulos por columna ≤ `quality.max_null_percentage` (5 %). Los nulos estructurales (por ejemplo `edad_max` en tramos abiertos) se declaran y se controlan con una regla propia. | `QLT-002`, `edad_max_estructural`, `valores_no_nulos` |
| **Duplicados** | Clave de negocio única en cada conjunto. Las duplicaciones conocidas de la fuente (INE 6566) se eliminan de forma documentada. | `clave_unica`, `fact_clave_unica` (MOD-07), `ESC-04` |
| **Rangos válidos** | No negatividad de stocks y eventos; rangos plausibles por indicador en el catálogo; rangos por métrica de Eurostat; pensión media entre 100 y 5 000 €. | `MOD-11`, `ESC-08`, `rangos_validos`, `pension_media_coherente` |
| **Fechas** | `anyo`/`mes` coherentes con `fecha_referencia`, sin fechas futuras, cortes anuales en diciembre y alineación de 1 día en la tasa de afiliación. | `fechas_coherentes`, `corte_anual_en_mes_de_referencia`, `fechas_alineadas` |
| **Integridad referencial** | En memoria: toda FK existe en su dimensión. En la base: `FOREIGN KEY` declaradas y `PRAGMA foreign_key_check`. | `MOD-08`, `ESC-05`, `CAR-02` |
| **Consistencia entre fuentes** | Población del INE frente a Eurostat; gasto/PIB calculado frente al publicado; número de pensiones frente a importe (mismos periodos); anual frente a mensual de diciembre. | `MOD-W1`, `consistencia_publicado`, `periodos_iguales_a_numero`, `anual_igual_a_mensual_de_referencia` |
| **Coherencia interna** | Los KPIs se recalculan con sus componentes; los grupos suman el total; hombres + mujeres = total; el detalle cuadra con los totales publicados. | `MOD-14`, `MOD-15`, `ESC-09/10`, `totales_por_edad`, `clases_suman_total` |
| **Registros inesperados** | Mapeos estrictos: una etiqueta, variable, flag, unidad o territorio no documentado **detiene** Plata en lugar de pasar en silencio. Columnas no previstas en Excel o JSON-stat también detienen el proceso. | `IneNormalizer`, `EurostatNormalizer`, `PensionesParser._value_columns` |
| **Conteo antes y después** | Cada integración compara las filas de salida con la suma de las filas de origen; la carga compara Parquet, SQLite y CSV. | `fact_filas_conservadas` (MOD-09), `ESC-06`, `CAR-01`; métricas `filas_entrada/salida_por_conjunto` |
| **Completitud (KR 1.2)** | Años presentes / años esperados por serie (indicador × sexo × grupo), con la cobertura del catálogo. | `QLT-003 completitud_temporal` |
| **Atípicos** | Z-score modificado de las variaciones interanuales (\|z\| > 3,5): **solo advierte**. | `MOD-W2 atipicos` |
| **Integridad de Bronce** | Cada payload en exactamente un manifiesto, con el mismo tamaño y sha256; sin huérfanos. | `integridad_bronce` |
| **Linaje coherente** | Los indicadores proceden de la misma ejecución de Plata que se lee; las dimensiones de escenarios proceden del mismo modelo. | `MOD-00`, `ESC-00` |

## 10.2 Resultados de la ejecución real

Ejecución `pipeline_20260929T233337.118518Z` (`python main.py`, las 3 fuentes descargadas en ese momento): **completada en 80 s**. La salida de consola está en `logs/ejecucion_validacion_final.txt` y el registro en `logs/ejecuciones/`.

| Paso | Reglas | Resultado | Filas escritas | Conteo antes → después |
| --- | --- | --- | --- | --- |
| Integridad de Bronce | payload ↔ manifiesto | ✅ | — | INE 13, SS 2 y Eurostat 3 payloads por ejecución, sin huérfanos |
| Plata INE | 10 | ✅ 10/10 | 142 030 | población 141 597 · esperanza de vida 150 + 150 · ICF 50 · nacimientos 33 · defunciones 33 · saldo migratorio 17 |
| Plata Seguridad Social | 33 | ✅ 33/33 | 500 + 31 + 31 | afiliados 1985-01 a 2026-08 (500 meses); pensiones e importe: 10 anuales + 21 mensuales |
| Plata Eurostat | 10 | ✅ 10/10 | 162 | entrada 31 + 65 + 66 observaciones JSON-stat = salida 162 |
| Indicadores demográficos | 12 | ✅ 12/12 | 1 885 | 4 KPIs de estructura × (55 años observados + 8 escenarios × 51 años) = 1 852, más 33 saldos vegetativos observados |
| Indicadores de pensiones | 11 | ✅ 11/11 | 10 | 2016-2025 |
| Indicadores integrados | 11 (+1 advertencia posible) | ✅ 11/11 · 0 advertencias | 70 | gasto/PIB 30 años + afiliación 40 años |
| Modelo | 22 (+2 advertencias) | ✅ 22/22 · 1 regla con advertencias (43 atípicos) | 1 563 hechos | orígenes: población 660 + INE publicados 433 + KPIs 253 + afiliados 41 + pensiones 40 + integrados 70 + macro 66 = **1 563** |
| Escenarios | 16 | ✅ 16/16 | 6 528 | población 4 896 + KPIs 1 632 = **6 528** |
| Carga | 3 | ✅ 3/3 | 14 tablas + 3 vistas | Parquet = SQLite = CSV en las 14 tablas; `foreign_key_check` vacío |

**Métricas de los OKR de calidad:**

- Completitud temporal mínima: **100 %** en las 36 series observadas y en todas las series proyectadas.
- Nulos en `fact_indicadores_anual`: **0 %**.
- Diferencia entre la población del INE y la de Eurostat: máximo **0,0002 %** en 55 años.
- Diferencia entre el gasto/PIB calculado y el publicado por Eurostat: máximo **0,0050 pp**.

### Advertencias: atípicos detectados (no se corrigen)

Los 43 hallazgos corresponden a acontecimientos reales, lo que confirma que la regla detecta cambios bruscos sin falsos positivos por tendencia:

- **COVID-19 (2020-2021):** defunciones +75 073, esperanza de vida −1,25 años, PIB −124 496 M€, gasto/PIB +1,76 pp y número de pensiones casi estancado (+7 640, frente a unas +100 000 anuales habituales).
- **Crisis de 2008-2014:** afiliados −890 142 (2008), −665 595 (2009), −779 304 (2012); caída de la población de 16-64 años en 2013-2015.
- **Ciclo inmigratorio 2003-2008:** saltos de la población de 16-64 años.
- **Ruptura y repunte migratorio de 2022** (cambio de operación estadística en 2021).
- **Revalorización de las pensiones de 2023-2024:** gasto en pensiones +18 520 M€ en 2023; pensiones +169 486 en 2024.

## 10.3 Hallazgo de calidad corregido durante la validación

La regla nueva `MOD-15 sexos_suman_total` **detuvo** la primera ejecución del modelo: en 1976, 1981 y 1987 la población de 65+ de hombres + mujeres no coincidía con el total.

- **Diagnóstico:** el INE publica cada celda (edad × sexo) redondeada; entre 1971 y 2012 hay diferencias de ±1 persona por edad, que suman como máximo 12 personas en un año (sobre unos 34 M).
- **Decisión:** no se corrige el dato. Se aplica una tolerancia **absoluta y documentada** de 16 personas (`modelo.tolerancia_suma_sexos_personas`), la misma que el repositorio ya usaba para la tabla 56934 antes de julio de 2012.
- **Evidencia:** la regla pasa y sigue detectando cualquier diferencia mayor.

## 10.4 Pruebas automatizadas

`python -m pytest` ejecuta **292 pruebas deterministas sin acceso a la red**, con dobles de las tres fuentes en `tests/fakes/`. Cubren:

- **Extractores:** bytes originales, manifiestos, errores HTTP, respuestas vacías o de error, hojas ausentes y cierre de la conexión (también cuando la extracción falla).
- **EDA de datos originales:** conversión de Bronce a DataFrames sin limpiar (notas al pie, secciones de porcentajes, copias de la 6566 y flags se conservan).
- **Programación:** frecuencias de `schedule`, validación de la configuración, ejecución programada con reloj simulado, registro JSONL y aislamiento de fallos.
- **Plata:** mapeos estrictos, duplicados, rupturas, cobertura, rechazo sin escritura.
- **Indicadores:** fórmulas, numerador/denominador, desfase de fechas, advertencia del valor publicado.
- **Modelo:** claves deterministas, rechazo de duplicados, FK huérfanas, fuera de rango, incoherencia, datos proyectados en el modelo y linaje obsoleto.
- **Escenarios:** solo demografía oficial, dimensiones conformadas, *mart* frente a la base y frente al último observado.
- **Carga:** PK y FK aplicadas por el motor, vistas, CSV, DDL de PostgreSQL y rechazo de un Parquet alterado.
- **Pipeline completo** desde Plata y desde Bronce (extractores simulados), `--hasta`, fallos y registro.
- **Documentación generada** sincronizada con el código.

## 10.5 Lo que no se pudo verificar

- **Carga en PostgreSQL.** Los scripts `01_ddl.sql` y `02_carga.sql` se generan desde el mismo contrato que la base SQLite verificada y las pruebas comprueban su contenido, pero **no se ejecutaron contra un servidor PostgreSQL**, porque no había ninguno disponible en el equipo de desarrollo.
- **Notebook.** Se ejecutó de principio a fin con descarga en vivo de las tres fuentes; sus cifras dependen de la publicación vigente de cada fuente. Sin red, reutiliza el último Bronce completado (`--sin-red`).
- **Estabilidad de las fuentes.** Las URL de la Seguridad Social cambian cada mes y las APIs pueden cambiar de formato. Los validadores de Bronce y Plata detienen el pipeline con un mensaje explícito si ocurre, pero no pueden anticiparlo.
