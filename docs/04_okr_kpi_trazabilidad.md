# 4. OKRs, KPIs y trazabilidad

## 4.1 OKRs revisados

| Objetivo | Resultado clave | Cómo se mide en el pipeline | Resultado (ejecución 29/09/2026) |
| --- | --- | --- | --- |
| **O1. Integrar en una única base las fuentes oficiales demográficas, laborales y de pensiones, con calidad y trazabilidad.** | **KR 1.1** (revisado, R1): 3 fuentes oficiales núcleo con extracción automatizada y manifiesto de auditoría. | Pasos `bronce_*` y manifiestos en `data/bronze/*/manifests/`. | ✅ INE (13 payloads), Seguridad Social (2) y Eurostat (3); integridad verificada. |
| | **KR 1.2**: completitud ≥ 95 % en las tablas de hechos, sin nulos indebidos ni valores fuera de rango. | Reglas `QLT-002` (nulos por columna), `QLT-003` (años presentes / cobertura esperada, por serie) y `MOD-11` (rangos). | ✅ Completitud temporal mínima de **100 %** en las 36 series del modelo; 0 % de nulos en `fact_indicadores_anual`; 0 valores fuera de rango. |
| | **KR 1.3**: 100 % de las transformaciones y del linaje documentados. | Manifiesto por conjunto (entradas con sha256, `run_id`); `run_id_origen` y `gold_run_id` por fila; `aux_linaje`; documentos 06 y 08. | ✅ 12 conjuntos de Oro con linaje hasta Bronce; documentación generada y probada. |
| **O2. Construir un conjunto de indicadores y la base del tablero para monitorear el riesgo demográfico y la sostenibilidad.** | **KR 2.1**: 8 KPIs cargados desde el pipeline, con actualización automatizada. | `dim_indicador.tipo_indicador = 'kpi'`; regla `MOD-05`. | ✅ KPI-01 a KPI-08 disponibles. |
| | **KR 2.2**: tablero con pestañas Demografía, Cotización/Pensiones y Sostenibilidad financiera. | `dim_indicador.pestana_tablero`; guía [11](11_guia_power_bi.md). | ⏳ Datos y modelo listos; el tablero se construye en la siguiente entrega. |
| **O3. Habilitar el uso analítico para preguntas estratégicas sobre la sostenibilidad del sistema.** | **KR 3.1** (revisado, R3): integrar en una capa separada los escenarios **oficiales** del INE (base, optimista y pesimista, 2030-2050), sin modelación propia. | Capa `data/gold/escenarios/`; reglas `ESC-01` a `ESC-13`. | ✅ 8 escenarios INE; *mart* 2030-2050 con 504 filas. |
| | **KR 3.2**: informe ejecutivo reproducible. | Notebook único `notebooks/Proyecto_ETL_Pensiones_Espana.ipynb` en 7 partes: extracción de las 3 fuentes, comprensión y perfil de calidad del dato original, estadísticos, 15 preguntas de negocio, transformación Medallion y automatización. | ✅ Ejecutado de principio a fin sobre la ejecución real. |

## 4.2 Ficha de los 8 KPIs

Para cada KPI: qué mide, variables, fuentes, transformaciones, fórmula, periodicidad, granularidad, dimensiones, tabla Oro y verificación. La unidad, la cobertura, el rango y la referencia temporal están en el [diccionario de métricas](05_diccionario_metricas.md).

### KPI-01 · Índice de envejecimiento (`indice_envejecimiento`)
- **Qué mide.** El peso de la población mayor frente a la joven. Es la señal estructural más directa del envejecimiento.
- **Variables y fuente.** Población a 1 de enero por edad simple (INE 56934); proyecciones de las tablas 36643 y 36652.
- **Transformaciones.**
  1. Plata: selecciona el 1 de enero, particiona las edades y homologa el tramo abierto.
  2. Indicadores: `DemografiaKpis.age_groups` suma las edades en los grupos 0-15, 16-64 y 65+.
- **Fórmula.** `poblacion(65+) / poblacion(0-15) × 100`.
- **Periodicidad y granularidad.** Anual; España.
- **Dimensiones.** Tiempo y territorio (y escenario en la capa de escenarios).
- **Oro.** `kpis_demograficos` → `fact_indicadores_anual`, `dm_panel_anual`, `fact_proyecciones_demograficas`.
- **Verificación.**
  - `MOD-14` recalcula el KPI con la población por grupo del propio modelo; `ESC-09` hace lo mismo por escenario.
  - Valores: 32,84 (1971) → **148,05 (2025)** → 249,57 en 2050 (escenario base).

### KPI-02 · Tasa de dependencia demográfica (`tasa_dependencia`)
- **Qué mide.** Cuántas personas en edades potencialmente inactivas hay por cada 100 en edad de trabajar.
- **Variables y fuente.** Las mismas que el KPI-01.
- **Fórmula.** `(poblacion(0-15) + poblacion(65+)) / poblacion(16-64) × 100`.
- **Periodicidad, dimensiones y Oro.** Como el KPI-01.
- **Verificación.** `MOD-14`/`ESC-09`. Valores: 64,21 (1971) → **53,17 (2025)** → 72,56 en 2050 (base).
- **Interpretación.** Baja hasta 2025 porque cae la dependencia juvenil, no porque mejore la sostenibilidad; por eso se acompaña del KPI-03.

### KPI-03 · Tasa de dependencia de mayores (`tasa_dependencia_mayores`)
- **Qué mide.** La presión de la población de 65+ sobre la población en edad de trabajar. Es el indicador demográfico más cercano a un sistema de reparto.
- **Fórmula.** `poblacion(65+) / poblacion(16-64) × 100`.
- **Periodicidad, dimensiones y Oro.** Como el KPI-01.
- **Verificación.** `MOD-14`/`ESC-09`. Valores: 15,87 (1971) → **31,73 (2025)** → 51,81 en 2050 (base).

### KPI-04 · Indicador coyuntural de fecundidad (`indicador_coyuntural_fecundidad`)
- **Qué mide.** Los hijos por mujer con la fecundidad por edad del año. El umbral de reemplazo es aproximadamente 2,1.
- **Fuente.** INE 1407 (Indicadores Demográficos Básicos), con nacionalidad = ambas y orden = todos.
- **Transformación.** Normalización estricta. **No se recalcula**, porque exige tasas específicas por edad de la madre que el INE publica con su metodología.
- **Fórmula (INE).** `Σ_x f_x`, la suma de las tasas específicas de fecundidad por edad x.
- **Periodicidad, dimensiones y Oro.** Anual; tiempo y territorio; `fact_indicadores_anual` y `dm_panel_anual`.
- **Verificación.** Rango [0,5, 5] (`MOD-11`). Valores: 2,77 (1975) → **1,10 (2024)**.

### KPI-05 · Saldo vegetativo (`saldo_vegetativo`)
- **Qué mide.** El crecimiento natural de la población.
- **Fuente.** INE 6566, con las copias duplicadas deduplicadas en Plata.
- **Fórmula.** `nacimientos − defunciones`.
- **Oro.** `kpis_demograficos` → modelo.
- **Verificación.** `MOD-14` lo recalcula con los componentes del modelo. Valores: +65 232 (1992) → **−118 113 (2024)**.

### KPI-06 · Saldo migratorio con el extranjero (`saldo_migratorio_exterior`)
- **Qué mide.** El crecimiento migratorio neto, que en las proyecciones del INE es el único motor del crecimiento de la población.
- **Fuentes.** INE 24309 (2008-2020) y 69758 (2021-).
- **Transformación.** Reconciliación del solapamiento de 2021. **No se homogeneiza la unidad**: `metodologia` = `ine_24309` / `ine_69758`.
- **Fórmula (INE).** `inmigraciones del extranjero − emigraciones al extranjero`.
- **Verificación.** `MOD-13 fact_unidad_homogenea` por metodología; el salto de 2022 aparece marcado como atípico. Valores: 310 641 (2008) → **626 268 (2024)**.
- **Limitación.** Ruptura de serie en 2021.

### KPI-07 · Ratio afiliados por pensión contributiva (`ratio_cotizantes_pensionistas`)
- **Qué mide.** Cuántas situaciones de afiliación en alta hay por cada pensión contributiva. Es la aproximación oficial y automatizable al equilibrio de un sistema de reparto.
- **Fuentes.** TGSS (afiliados en alta a 31/12) e INSS (pensiones en vigor a 1/12).
- **Transformaciones.**
  1. Plata: parsers por encabezado.
  2. Indicadores: stock de diciembre, con prioridad al corte anual publicado.
- **Fórmula.** `afiliados_31dic / pensiones_1dic`.
- **Oro.** `kpi_ratio_sostenibilidad_anual` → modelo.
- **Verificación.** `SS-KPI ratio_coherente`, `metodologia_homogenea` y `MOD-14`. Valores: 1,873 (2016) → **2,078 (2025)**.
- **Limitación.** Mide por **pensión**, no por **pensionista** (ver §4.4).

### KPI-08 · Gasto en pensiones sobre el PIB (`gasto_pensiones_pib`)
- **Qué mide.** El esfuerzo económico que supone el sistema de pensiones.
- **Fuente.** Eurostat: `spr_exp_pens` (TOTAL, millones de €) y `nama_10_gdp` (B1GQ, precios corrientes).
- **Transformaciones.**
  1. Plata: JSON-stat a formato largo, con los flags `p` mapeados a provisional.
  2. Indicadores: cociente, conservando numerador, denominador y el % publicado por Eurostat.
- **Fórmula.** `gasto_pensiones / pib × 100`.
- **Oro.** `kpis_integrados_anual` → modelo.
- **Verificación.** `INT-QLT coherencia_calculo`, `consistencia_publicado` (diferencia máxima con Eurostat: **0,0050 pp**) y `MOD-14`. Valores: 9,82 % (1995) → 14,39 % (2020) → **13,23 % (2024, provisional por el PIB)**.

## 4.3 Matriz de trazabilidad OKR → KPI → datos → transformación → Oro

| OKR | KPI | Fórmula | Fuente (tabla o conjunto) | Transformación (capa · módulo) | Tabla Oro | Dimensiones | Disponible |
| --- | --- | --- | --- | --- | --- | --- | --- |
| O2 / KR 2.1 | KPI-01 Índice de envejecimiento | P65+ / P0-15 × 100 | INE 56934 (+ 36643/36652) | Plata `DemografiaTransform` → Indicadores `DemografiaKpis` | `fact_indicadores_anual`, `dm_panel_anual`, `fact_proyecciones_demograficas` | tiempo, territorio (+ escenario) | ✅ 1971-2025 · proyección 2026-2076 |
| O2 / KR 2.1 | KPI-02 Tasa de dependencia | (P0-15 + P65+) / P16-64 × 100 | INE 56934 (+ 36643/36652) | Ídem | Ídem | tiempo, territorio (+ escenario) | ✅ 1971-2025 · 2026-2076 |
| O2 / KR 2.1 | KPI-03 Dependencia de mayores | P65+ / P16-64 × 100 | INE 56934 (+ 36643/36652) | Ídem | Ídem | tiempo, territorio (+ escenario) | ✅ 1971-2025 · 2026-2076 |
| O2 / KR 2.1 | KPI-04 ICF | Σ tasas de fecundidad por edad (INE) | INE 1407 | Plata `IneNormalizer` (constantes estrictas) | `fact_indicadores_anual`, `dm_panel_anual` | tiempo, territorio | ✅ 1975-2024 |
| O2 / KR 2.1 | KPI-05 Saldo vegetativo | Nacimientos − Defunciones | INE 6566 | Plata (deduplicación) → Indicadores `DemografiaKpis` | Ídem | tiempo, territorio | ✅ 1992-2024 |
| O2 / KR 2.1 | KPI-06 Saldo migratorio | Inmigraciones − Emigraciones (INE) | INE 24309 + 69758 | Plata `PoblacionConsolidator` (reconciliación de 2021) | Ídem | tiempo, territorio | ✅ 2008-2024 (ruptura en 2021) |
| O2 / KR 2.1 | KPI-07 Afiliados por pensión | Afiliados 31/12 / Pensiones 1/12 | TGSS afiliados + INSS avance mensual | Plata `AfiliadosParser`, `PensionesParser` → Indicadores `RatioCotizantesPensionistas` | Ídem | tiempo, territorio | ✅ 2016-2025 |
| O2 / KR 2.1 | KPI-08 Gasto en pensiones / PIB | Gasto ESSPROS / PIB × 100 | Eurostat `spr_exp_pens` + `nama_10_gdp` | Plata `JsonStatParser`, `EurostatNormalizer` → Indicadores `IndicadoresIntegrados` | Ídem + `aux_kpis_integrados` | tiempo, territorio | ✅ 1995-2024 (2023-2024 provisional) |
| O2 (contexto) | % población 65+ | P65+ / P total × 100 | INE 56934 (+ proyecciones) | Indicadores `DemografiaKpis` | modelo + escenarios | tiempo, territorio (+ escenario) | ✅ 1971-2025 · 2026-2076 |
| O2 (contexto) | Esperanza de vida 0 / 65 | Publicada por el INE | INE 1414 / 1415 | Plata (edad como constante) | modelo | tiempo, territorio, **sexo** | ✅ 1975-2024 |
| O2 (contexto) | Tasa de afiliación 16-64 | Afiliados 31/12 t / P16-64 1/1 t+1 × 100 | TGSS + INE 56934 | Indicadores `IndicadoresIntegrados` | modelo | tiempo, territorio | ✅ 1985-2024 |
| O2 (contexto) | Pensión media | Importe × 1000 / Pensiones | INSS (número e importe) | Indicadores `RatioCotizantesPensionistas` | modelo | tiempo, territorio | ✅ 2016-2025 |
| O1 / KR 1.2 | Completitud de las tablas de hechos | Años presentes / esperados por serie | Todas | `ModeloQuality._temporal` | reporte + `aux_calidad_reglas` | indicador, sexo, grupo | ✅ mínimo 100 % |
| O1 / KR 1.3 | Linaje documentado | Conjuntos con manifiesto y `run_id` de entrada | Todas | Manifiestos por capa | `aux_linaje` | capa, conjunto | ✅ 12/12 |
| O3 / KR 3.1 | Escenarios oficiales 2030-2050 | Proyección INE; diferencia frente a la base | INE 36643/36652 | Escenarios `Proyecciones` | `dm_escenarios_2050` | tiempo, escenario, grupo de edad | ✅ base/optimista/pesimista + 5 de sensibilidad |

## 4.4 KPIs que no se pueden calcular con rigor tal como estaban definidos

| KPI original | Problema | Modificación técnicamente justificada |
| --- | --- | --- |
| «Ratio de cotizantes / pensionistas = afiliados en alta / pensionistas» | 1) Las fuentes automatizables publican **afiliados** (situaciones de alta, no cotizantes únicos) y **pensiones** (no pensionistas únicos). 2) La serie de pensionistas solo aparece en notas de prensa mensuales, sin serie descargable estable. | Se calcula **afiliados en alta por pensión contributiva** con stocks de diciembre y se renombra en `dim_indicador` para que no se confunda. No se estima el número de pensionistas (no se inventan datos). Diferencia de orden de magnitud: 22,46/9,49 ≈ 2,37 por pensionista frente a 2,08 por pensión. |
| «Gasto público en pensiones / PIB» | El gasto de la nómina contributiva del INSS no incluye pagas extraordinarias, clases pasivas ni pensiones no contributivas, y no existe como serie anual en el libro descargado. | Se usa el **gasto en pensiones ESSPROS de Eurostat**, que es anual, armonizado y en el mismo marco que el PIB. La nómina mensual del INSS se conserva como métrica base (`importe_nomina_pensiones`) y para la pensión media. |

## 4.5 Preguntas de negocio reformuladas

| Pregunta original (Avance 1) | Problema (R4) | Pregunta que responde la base | Indicadores |
| --- | --- | --- | --- |
| ¿Cómo evolucionará la relación cotizante/pensionista en 2030-2050? | Exige proyectar empleo y pensiones: es modelación. | ¿Cómo ha evolucionado la relación afiliados/pensión desde 2016 y cuánto aumenta la **presión demográfica** (dependencia de mayores) en los escenarios oficiales del INE hasta 2050? | KPI-07 (observado), KPI-03 (escenarios) |
| ¿Cuál será el impacto neto de 3,7 M de jubilados no reemplazados? | Impacto causal, con supuestos laborales y fiscales. | ¿Cómo cambia la población de 16-64 frente a la de 65+ (observada y proyectada) y cómo ha evolucionado la tasa de afiliación? | población por grupo, tasa de afiliación |
| ¿A qué ritmo se aproxima el gasto al 17,3 % del PIB en 2050? | Exige proyección fiscal (Ageing Report, AIReF). | ¿Cuál ha sido la trayectoria del gasto en pensiones sobre el PIB entre 1995 y 2024, y qué relación guarda con la dependencia de mayores? | KPI-08, KPI-03 |
| ¿En qué medida la inmigración reduce el déficit? | Causal; requiere datos de cotización por nacionalidad. | ¿Qué peso tiene el saldo migratorio frente al saldo vegetativo en el crecimiento de la población? | KPI-05, KPI-06 |
| Impactos regionales | Sin datos regionales en el MVP. | Fuera del MVP; `dim_territorio` admite CCAA ([12](12_limitaciones_y_proximos_pasos.md)). | — |

## 4.6 Tipo de información en la base

Para no confundir datos con interpretaciones, cada elemento de la base pertenece a una de estas categorías:

| Categoría | Qué es | Ejemplos en la base | Cómo se identifica |
| --- | --- | --- | --- |
| **Dato observado** | Valor publicado por la fuente, sin cambios salvo el tipo o la unidad declarada. | Población por edad, nacimientos, afiliados, pensiones, PIB, ICF, esperanza de vida | `estado_dato = observado`; `metodologia` = tabla de origen |
| **Dato provisional** | Publicado por la fuente como provisional o estimado. | PIB 2023-2025; gasto/PIB 2023-2024 | `estado_dato = provisional`; `tiene_datos_provisionales` en el panel |
| **Dato transformado** | Reorganizado sin cambiar su significado (agregación de edades, stock de diciembre, reconciliación de tablas). | Población por grupo de edad; afiliados a 31/12; saldo migratorio 2008-2024 | `metodologia` (`suma_edades_simples_*`, `stock_31_diciembre`, `ine_24309` / `ine_69758`) |
| **Cálculo derivado** | KPI calculado por el pipeline con una fórmula del catálogo. | KPI-01, 02, 03, 05, 07 y 08; % 65+, tasa de afiliación, pensión media | `dim_indicador.formula`; `dataset_origen` de la capa de indicadores |
| **Proyección oficial** | Escenario publicado por el INE; no es un dato ni un cálculo propio. | `fact_proyecciones_demograficas` | `estado_dato = proyectado`; `dim_escenario.fuente_oficial` |
| **Supuesto** | Decisión metodológica del pipeline. | Grupos 0-15 / 16-64 / 65+; afiliación de 31/12 con población de 1/1 del año siguiente; tolerancias de redondeo | `config.yaml` (comentado) y este documento |
| **Limitación** | Algo que los datos no permiten afirmar. | Afiliados por pensión frente a por pensionista; ruptura migratoria; datos solo nacionales | [12](12_limitaciones_y_proximos_pasos.md) |
| **Interpretación** | Lectura analítica de los datos. | «La dependencia total baja hasta 2025 por la caída de la juvenil» | Solo en la documentación y los notebooks; nunca en las tablas |
