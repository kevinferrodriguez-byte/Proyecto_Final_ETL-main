# Catálogo de reglas de calidad

Además de estas reglas, cada capa comprueba el esquema (`QLT-001`: columnas, tipos, nulos obligatorios y dominios) antes de evaluar el resto y la integridad de Bronce (sha256 y tamaño de cada payload frente a su manifiesto) antes de promover datos a Plata. Una regla en `falla` detiene la escritura de la capa; las marcadas como advertencia (atípicos, consistencia entre fuentes) se registran sin detener el pipeline.

## Plata INE (`stg_poblacion_anual`)

| Regla | Criterio |
| --- | --- |
| `valores_no_nulos` | SLV-005: ninguna fila sin valor |
| `fraccion_nulos` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage; edad_max es nula por diseño y la controla edad_max_estructural |
| `no_negativos` | QLT-002: población, nacimientos y defunciones no negativos |
| `edad_max_estructural` | QLT-002: edad_max nula solo en tramos abiertos y totales |
| `clave_unica` | SLV-005: clave de negocio sin duplicados |
| `sin_mezcla_observado_proyectado` | SLV-005: ninguna clave mezcla observado y proyectado |
| `totales_por_edad` | SLV-005: detalle igual a 'Todas las edades' dentro de la tolerancia aprobada |
| `tramo_homologado` | SLV-003: tramo homologado igual a la suma de sus componentes |

## Plata Seguridad Social · afiliados (`stg_afiliados_mensual`)

| Regla | Criterio |
| --- | --- |
| `valores_no_nulos` | SS-QLT: todo mes tiene total_afiliados |
| `fraccion_nulos` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage |
| `valores_positivos` | SS-QLT: total_afiliados mayor que cero |
| `mes_valido` | SS-QLT: mes entre 1 y 12 |
| `fechas_coherentes` | SS-QLT: anyo y mes coinciden con fecha_referencia (último día del mes) y ninguna fecha es futura |
| `clave_unica` | SS-QLT: una fila por territorio, año y mes |
| `completitud_temporal` | SS-QLT: meses presentes dentro de la cobertura esperada >= quality.min_temporal_completeness |

## Plata Seguridad Social · pensiones (`stg_pensiones_cuantia`)

| Regla | Criterio |
| --- | --- |
| `valores_no_nulos` | SS-QLT: toda fila tiene el total y las cinco clases de pensión |
| `fraccion_nulos` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage |
| `total_positivo` | SS-QLT: total_pensiones mayor que cero |
| `clases_no_negativas` | SS-QLT: pensiones por clase no negativas |
| `mes_valido` | SS-QLT: mes entre 1 y 12 |
| `corte_anual_en_mes_de_referencia` | SS-QLT: las filas anuales usan el mes de la nota de la fuente (annual_reference.month) |
| `fechas_coherentes` | SS-QLT: anyo y mes coinciden con fecha_referencia (día 1 del mes) y ninguna fecha es futura |
| `clave_unica` | SS-QLT: una fila por territorio, tipo de corte, año y mes |
| `clases_no_superan_total` | SS-QLT: ninguna clase de pensión supera total_pensiones |
| `clases_suman_total` | SS-QLT: las cinco clases de pensión suman total_pensiones |
| `anual_igual_a_mensual_de_referencia` | SS-QLT: el dato anual coincide con el mensual del mes de referencia cuando ambos existen |
| `completitud_temporal_anual` | SS-QLT: años presentes dentro de la cobertura anual esperada >= quality.min_temporal_completeness |
| `completitud_temporal_mensual` | SS-QLT: meses presentes dentro de la cobertura mensual esperada >= quality.min_temporal_completeness |

## Plata Seguridad Social · importe (`stg_pensiones_importe`)

| Regla | Criterio |
| --- | --- |
| `valores_no_nulos` | SS-QLT: toda fila tiene el importe total y el de las cinco clases |
| `fraccion_nulos` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage |
| `total_positivo` | SS-QLT: importe_total mayor que cero |
| `clases_no_negativas` | SS-QLT: importe por clase no negativo |
| `fechas_coherentes` | SS-QLT: anyo y mes coinciden con fecha_referencia (día 1 del mes) y ninguna fecha es futura |
| `clave_unica` | SS-QLT: una fila por territorio, tipo de corte, año y mes |
| `clases_suman_total` | SS-QLT: las cinco clases suman importe_total dentro de importe.sum_tolerance (miles de euros) |
| `periodos_iguales_a_numero` | SS-QLT: el importe cubre exactamente los mismos periodos que el número de pensiones (consistencia entre hojas) |
| `completitud_temporal_anual` | SS-QLT: años presentes dentro de la cobertura anual esperada >= quality.min_temporal_completeness |

## Plata Eurostat (`stg_macro_anual`)

| Regla | Criterio |
| --- | --- |
| `valores_no_nulos` | EUR-QLT: toda observación tiene valor |
| `fraccion_nulos` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage (flag_eurostat es nulo por diseño) |
| `no_negativos` | EUR-QLT: PIB, gasto y población no negativos |
| `rangos_validos` | EUR-QLT: cada métrica dentro de su rango plausible (sources.eurostat.valid_ranges) |
| `clave_unica` | EUR-QLT: una fila por conjunto, métrica, territorio y año |
| `fechas_coherentes` | EUR-QLT: fecha_referencia pertenece al año y no es futura |
| `unidad_homogenea` | EUR-QLT: una unidad por métrica |
| `completitud_temporal` | QLT-003: años presentes / esperados >= quality.min_temporal_completeness por conjunto y métrica |

## Oro · indicadores demográficos (`kpis_demograficos`)

| Regla | Criterio |
| --- | --- |
| `valores_no_nulos` | GLD-006: todos los KPIs tienen valor |
| `fraccion_nulos` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage |
| `denominadores_positivos` | GLD-006 y QLT-002: población menor de 16 y de 16 a 64 años mayor que cero |
| `edades_asignadas` | GLD-002: toda fila de detalle pertenece a un grupo de edad por rango numérico |
| `grupos_suman_total` | GLD-002: los tres grupos de edad suman la población total de detalle |
| `poblacion_no_negativa` | QLT-002: población por grupo de edad no negativa |
| `eventos_completos` | GLD-005: cada año con nacimientos tiene defunciones y viceversa, sin valores negativos |
| `saldo_solo_observado` | GLD-005: el saldo vegetativo solo se calcula con datos observados |
| `clave_unica` | GLD-001: una fila por año, territorio, escenario e indicador |
| `sin_mezcla_observado_proyectado` | GLD-006: observado y proyectado nunca comparten clave |

## Oro · indicadores de pensiones (`kpi_ratio_sostenibilidad_anual`)

| Regla | Criterio |
| --- | --- |
| `valores_no_nulos` | SS-KPI: todos los años tienen ratio |
| `fraccion_nulos` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage |
| `denominadores_positivos` | SS-KPI: total_pensiones mayor que cero (división por cero rechazada) |
| `ratio_positivo` | SS-KPI: ratio mayor que cero |
| `ratio_coherente` | SS-KPI: ratio igual a total_afiliados / total_pensiones |
| `metodologia_homogenea` | SS-KPI: numerador y denominador son stocks del mes de referencia en todos los años |
| `clave_unica` | SS-KPI: una fila por año, territorio y metodología |
| `cobertura_anual` | SS-KPI: años con ratio dentro de la cobertura esperada >= quality.min_temporal_completeness |
| `pension_media_coherente` | SS-KPI: pension_media_eur = importe_nomina_miles_eur × 1000 / total_pensiones, dentro de 100-5000 EUR |

## Oro · indicadores integrados (`kpis_integrados_anual`)

| Regla | Criterio |
| --- | --- |
| `valores_no_nulos` | INT-QLT: todo KPI integrado tiene valor, numerador y denominador |
| `fraccion_nulos` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage (valor_publicado solo existe para gasto/PIB) |
| `denominadores_positivos` | INT-QLT: denominadores (PIB, población 16-64) mayores que cero |
| `coherencia_calculo` | INT-QLT: valor = numerador / denominador × 100 |
| `rangos_validos` | INT-QLT: cada KPI dentro del rango del catálogo modelo.indicators |
| `clave_unica` | INT-QLT: una fila por año, territorio e indicador |
| `fechas_alineadas` | INT-QLT: en la tasa de afiliación, población a 1/1 del año siguiente a la afiliación de 31/12 (1 día) |
| `completitud_temporal` | QLT-003: años presentes / cobertura esperada del catálogo >= quality.min_temporal_completeness |
| `consistencia_publicado` | INT-QLT: gasto/PIB calculado frente al porcentaje publicado por Eurostat (advierte si supera max_diferencia_publicado_pp) |

## Oro · modelo (`modelo dimensional`)

| Regla | Criterio |
| --- | --- |
| `dimensiones_esquema` | MOD-01: columnas, tipos, nulos y dominios de cada dimensión |
| `dimensiones_clave_unica` | MOD-02: clave sustituta y código natural únicos en cada dimensión |
| `tiempo_continuo` | MOD-03: dim_tiempo sin huecos y con todos los años de los hechos |
| `grupos_edad_convencion` | MOD-04: grupos de edad contiguos desde 0 y coherentes con indicadores.demografia.age_groups |
| `catalogo_completo` | MOD-05: todo indicador de los hechos está en dim_indicador y los 8 KPIs tienen datos |
| `fact_esquema` | MOD-06: columnas, tipos, nulos y dominios de fact_indicadores_anual |
| `fact_clave_unica` | MOD-07: una fila por año, territorio, sexo, grupo de edad e indicador |
| `fact_fk_validas` | MOD-08: integridad referencial (toda clave foránea existe en su dimensión) |
| `fact_filas_conservadas` | MOD-09: cada fila de origen aparece exactamente una vez (conteo antes = después) |
| `fact_solo_observado` | MOD-10: el modelo solo contiene datos observados o provisionales (las proyecciones van a la capa de escenarios) |
| `fact_rangos_validos` | MOD-11: cada indicador dentro de su rango plausible del catálogo |
| `fact_desagregacion_valida` | MOD-12: cada indicador solo usa las desagregaciones (sexo, grupo de edad) declaradas en el catálogo |
| `fact_unidad_homogenea` | MOD-13: una unidad por indicador y metodología |
| `fact_coherencia` | MOD-14: KPIs coherentes con sus componentes dentro del modelo (fórmulas del catálogo) |
| `sexos_suman_total` | MOD-15: población de hombres + mujeres = total por grupo de edad (tolerancia de redondeo INE: modelo.tolerancia_suma_sexos_personas) |
| `completitud_vertical` | QLT-002: fracción de nulos por columna dentro de quality.max_null_percentage |
| `completitud_temporal` | QLT-003 / KR 1.2: años presentes / cobertura del catálogo >= quality.min_temporal_completeness |
| `panel_esquema` | MOD-16: columnas, tipos y nulos de dm_panel_anual |
| `panel_conciliado` | MOD-17: cada celda de dm_panel_anual coincide con su fila de fact_indicadores_anual |
| `consistencia_poblacion_ine_eurostat` | MOD-W1: población INE a 1 de enero frente a Eurostat demo_pjan (diferencia relativa máxima configurada) |
| `atipicos` | MOD-W2: variaciones interanuales atípicas en series observadas (z-score modificado; solo advierte) |

## Oro · escenarios (`capa de escenarios`)

| Regla | Criterio |
| --- | --- |
| `dim_escenario_esquema` | ESC-01: columnas, tipos y dominios de dim_escenario |
| `dim_escenario_mapeo` | ESC-02: escenarios presentes en los datos y escenario_kr igual a indicadores.demografia.escenario_kr |
| `fact_esquema` | ESC-03: columnas, tipos, nulos y dominios de fact_proyecciones_demograficas |
| `fact_clave_unica` | ESC-04: una fila por año, territorio, escenario, sexo, grupo de edad e indicador |
| `fact_fk_validas` | ESC-05: integridad referencial con dim_escenario y con las dimensiones conformadas del modelo |
| `fact_filas_conservadas` | ESC-06: cada fila de origen aparece exactamente una vez |
| `solo_indicadores_demograficos` | ESC-07: solo indicadores demográficos configurados (sin proyecciones laborales, fiscales ni macroeconómicas) |
| `rangos_validos` | ESC-08: valores dentro del rango plausible del catálogo |
| `coherencia` | ESC-09: KPIs proyectados coherentes con la población proyectada por grupo de edad en cada escenario |
| `sexos_suman_total` | ESC-10: población proyectada de hombres + mujeres = total |
| `completitud_temporal` | QLT-003: cada serie cubre todo el horizonte de las tablas proyectadas (>= quality.min_temporal_completeness) |
| `mart_esquema` | ESC-11: columnas, tipos, nulos y dominios de dm_escenarios_2050 |
| `mart_clave_unica` | ESC-12: sin duplicados en la clave de dm_escenarios_2050 |
| `mart_rango` | ESC-13: dm_escenarios_2050 cubre todos los años del rango en base, optimista y pesimista; base con diferencia 0 |

## Carga (`SQLite y CSV`)

| Regla | Criterio |
| --- | --- |
| `conteo_filas` | CAR-01: filas en SQLite y en CSV = filas de los Parquet de Oro (conteo antes y después de la carga) |
| `integridad_referencial` | CAR-02: PRAGMA foreign_key_check sin violaciones |
| `vistas_consultables` | CAR-03: las vistas de consumo se ejecutan y devuelven filas |

Total: 111 reglas específicas (más la comprobación de esquema de cada conjunto).
