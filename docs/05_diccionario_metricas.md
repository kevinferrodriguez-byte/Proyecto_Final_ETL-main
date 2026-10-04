# Diccionario de métricas
## Resumen

| Código | Indicador | Tipo | Fórmula | Frecuencia | Unidad | Fuente | Nivel de agregación | Cobertura observada | Tabla Oro |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KPI-01 | `indice_envejecimiento` · Índice de envejecimiento | kpi | poblacion(65+) / poblacion(0-15) × 100 | anual (1 de enero) | porcentaje | Instituto Nacional de Estadística (INE) | nacional; territorio | 1971–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| KPI-02 | `tasa_dependencia` · Tasa de dependencia demográfica | kpi | (poblacion(0-15) + poblacion(65+)) / poblacion(16-64) × 100 | anual (1 de enero) | porcentaje | Instituto Nacional de Estadística (INE) | nacional; territorio | 1971–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| KPI-03 | `tasa_dependencia_mayores` · Tasa de dependencia de mayores | kpi | poblacion(65+) / poblacion(16-64) × 100 | anual (1 de enero) | porcentaje | Instituto Nacional de Estadística (INE) | nacional; territorio | 1971–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| KPI-04 | `indicador_coyuntural_fecundidad` · Indicador coyuntural de fecundidad | kpi | Σ tasas específicas de fecundidad por edad de la madre (publicado por el INE, no recalculado) | anual (año natural) | hijos_por_mujer | Instituto Nacional de Estadística (INE) | nacional; territorio | 1975–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| KPI-05 | `saldo_vegetativo` · Saldo vegetativo | kpi | nacimientos - defunciones | anual (año natural) | personas | Instituto Nacional de Estadística (INE) | nacional; territorio | 1992–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| KPI-06 | `saldo_migratorio_exterior` · Saldo migratorio con el extranjero | kpi | inmigraciones procedentes del extranjero - emigraciones con destino al extranjero (publicado por el INE) | anual (año natural) | movimientos_migratorios (hasta 2020) / migraciones (desde 2021) | Instituto Nacional de Estadística (INE) | nacional; territorio | 2008–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| KPI-07 | `ratio_cotizantes_pensionistas` · Ratio afiliados en alta por pensión contributiva | kpi | afiliados en alta a 31/12 / pensiones contributivas en vigor a 1/12 | anual (diciembre) | afiliados_por_pension | Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) | nacional; territorio | 2016–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| KPI-08 | `gasto_pensiones_pib` · Gasto en pensiones sobre el PIB | kpi | gasto en pensiones ESSPROS (millones EUR) / PIB a precios corrientes (millones EUR) × 100 | anual (año natural) | porcentaje_pib | Eurostat (Oficina Estadística de la Unión Europea) | nacional; territorio | 1995–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `porcentaje_mayores_65` · Proporción de población de 65 y más años | contexto | poblacion(65+) / poblacion total × 100 | anual (1 de enero) | porcentaje | Instituto Nacional de Estadística (INE) | nacional; territorio | 1971–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `esperanza_vida_nacimiento` · Esperanza de vida al nacimiento | contexto | publicado por el INE (tablas de mortalidad), no recalculado | anual (año natural) | anos | Instituto Nacional de Estadística (INE) | nacional; territorio, sexo | 1975–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `esperanza_vida_65` · Esperanza de vida a los 65 años | contexto | publicado por el INE (tablas de mortalidad), no recalculado | anual (año natural) | anos | Instituto Nacional de Estadística (INE) | nacional; territorio, sexo | 1975–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `tasa_afiliacion_16_64` · Afiliados por cada 100 personas de 16 a 64 años | contexto | afiliados en alta a 31/12 del año t / poblacion(16-64) a 1/1 del año t+1 × 100 | anual (31 de diciembre) | porcentaje | Cálculo del pipeline a partir de fuentes oficiales de distinto organismo | nacional; territorio | 1985–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `pension_media_mensual` · Pensión contributiva media mensual | contexto | importe de la nómina mensual (miles EUR) × 1000 / número de pensiones | anual (diciembre) | eur_mes | Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) | nacional; territorio | 2016–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `poblacion` · Población residente a 1 de enero | metrica_base | suma de la población por edad simple (Estadística Continua de Población) | anual (1 de enero) | personas | Instituto Nacional de Estadística (INE) | nacional; territorio, sexo, grupo_edad | 1971–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `nacimientos` · Nacimientos | metrica_base | publicado por el INE (Movimiento Natural de la Población) | anual (año natural) | nacimientos | Instituto Nacional de Estadística (INE) | nacional; territorio | 1992–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `defunciones` · Defunciones | metrica_base | publicado por el INE (Movimiento Natural de la Población) | anual (año natural) | defunciones | Instituto Nacional de Estadística (INE) | nacional; territorio | 1992–2024 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `total_afiliados` · Afiliados en alta a la Seguridad Social (31 de diciembre) | metrica_base | afiliados en alta laboral el último día de diciembre (TOTAL SISTEMA) | anual (31 de diciembre) | afiliados | Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) | nacional; territorio | 1985–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `total_pensiones` · Pensiones contributivas en vigor (1 de diciembre) | metrica_base | suma de pensiones de incapacidad permanente, jubilación, viudedad, orfandad y favor familiar | anual (diciembre) | pensiones | Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) | nacional; territorio | 2016–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `importe_nomina_pensiones` · Importe mensual de la nómina de pensiones contributivas | metrica_base | importe de la nómina mensual de diciembre (TOTAL), publicado por el INSS | anual (diciembre) | miles_eur | Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) | nacional; territorio | 2016–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `pib` · Producto interior bruto a precios corrientes | metrica_base | B1GQ a precios de mercado, precios corrientes (SEC 2010) | anual (año natural) | millones_eur | Eurostat (Oficina Estadística de la Unión Europea) | nacional; territorio | 1995–2025 | `fact_indicadores_anual`, `dm_panel_anual` |
| — | `gasto_pensiones` · Gasto en pensiones (ESSPROS) | metrica_base | gasto total en pensiones del Sistema Europeo de Estadísticas Integradas de Protección Social | anual (año natural) | millones_eur | Eurostat (Oficina Estadística de la Unión Europea) | nacional; territorio | 1990–2024 | `fact_indicadores_anual`, `dm_panel_anual` |

## Ficha de cada indicador

### KPI-01 · Índice de envejecimiento (`indice_envejecimiento`)

Personas de 65 y más años por cada 100 menores de 16. Mide el envejecimiento de la estructura por edad.

- **Fórmula:** poblacion(65+) / poblacion(0-15) × 100
- **Unidad:** porcentaje · **Frecuencia:** anual · **Referencia temporal:** 1 de enero
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `kpis_demograficos`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1971–2025
- **Rango válido:** [0, 1000] · **Lectura:** mayor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** demografia

### KPI-02 · Tasa de dependencia demográfica (`tasa_dependencia`)

Población en edades potencialmente inactivas por cada 100 personas en edad de trabajar (16-64).

- **Fórmula:** (poblacion(0-15) + poblacion(65+)) / poblacion(16-64) × 100
- **Unidad:** porcentaje · **Frecuencia:** anual · **Referencia temporal:** 1 de enero
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `kpis_demograficos`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1971–2025
- **Rango válido:** [0, 200] · **Lectura:** mayor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** demografia

### KPI-03 · Tasa de dependencia de mayores (`tasa_dependencia_mayores`)

Personas de 65 y más años por cada 100 personas de 16 a 64 años. Aproxima la presión demográfica sobre un sistema de reparto.

- **Fórmula:** poblacion(65+) / poblacion(16-64) × 100
- **Unidad:** porcentaje · **Frecuencia:** anual · **Referencia temporal:** 1 de enero
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `kpis_demograficos`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1971–2025
- **Rango válido:** [0, 200] · **Lectura:** mayor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** demografia

### KPI-04 · Indicador coyuntural de fecundidad (`indicador_coyuntural_fecundidad`)

Número medio de hijos por mujer si se mantuvieran las tasas de fecundidad por edad del año. Umbral de reemplazo aproximado de 2,1.

- **Fórmula:** Σ tasas específicas de fecundidad por edad de la madre (publicado por el INE, no recalculado)
- **Unidad:** hijos_por_mujer · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `stg_poblacion_anual (tabla 1407)`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1975–2024
- **Rango válido:** [0.5, 5] · **Lectura:** menor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** demografia

### KPI-05 · Saldo vegetativo (`saldo_vegetativo`)

Crecimiento natural de la población. Negativo cuando las defunciones superan a los nacimientos.

- **Fórmula:** nacimientos - defunciones
- **Unidad:** personas · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `kpis_demograficos`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1992–2024
- **Rango válido:** [-1000000, 1000000] · **Lectura:** menor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** demografia

### KPI-06 · Saldo migratorio con el extranjero (`saldo_migratorio_exterior`)

Crecimiento migratorio neto con el extranjero. Ruptura de serie en 2021 (cambio de operación estadística del INE).

- **Fórmula:** inmigraciones procedentes del extranjero - emigraciones con destino al extranjero (publicado por el INE)
- **Unidad:** movimientos_migratorios (hasta 2020) / migraciones (desde 2021) · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `stg_poblacion_anual (tablas 24309 y 69758)`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 2008–2024
- **Rango válido:** [-2000000, 2000000] · **Lectura:** neutro · **OKR:** O2 · **Pestaña del tablero:** demografia

### KPI-07 · Ratio afiliados en alta por pensión contributiva (`ratio_cotizantes_pensionistas`)

Aproximación oficial al ratio cotizantes/pensionistas. El denominador son pensiones (una persona puede cobrar más de una), no pensionistas.

- **Fórmula:** afiliados en alta a 31/12 / pensiones contributivas en vigor a 1/12
- **Unidad:** afiliados_por_pension · **Frecuencia:** anual · **Referencia temporal:** diciembre
- **Fuente:** Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) · **Origen en el pipeline:** `kpi_ratio_sostenibilidad_anual`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 2016–2025
- **Rango válido:** [0.5, 10] · **Lectura:** menor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** cotizacion_pensiones

### KPI-08 · Gasto en pensiones sobre el PIB (`gasto_pensiones_pib`)

Esfuerzo de gasto en pensiones (vejez, jubilación anticipada, parcial, invalidez y supervivencia; ESSPROS) en relación con la economía.

- **Fórmula:** gasto en pensiones ESSPROS (millones EUR) / PIB a precios corrientes (millones EUR) × 100
- **Unidad:** porcentaje_pib · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Eurostat (Oficina Estadística de la Unión Europea) · **Origen en el pipeline:** `kpis_integrados_anual`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1995–2024
- **Rango válido:** [0, 30] · **Lectura:** mayor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** sostenibilidad_financiera

### contexto · Proporción de población de 65 y más años (`porcentaje_mayores_65`)

Peso de la población mayor sobre el total.

- **Fórmula:** poblacion(65+) / poblacion total × 100
- **Unidad:** porcentaje · **Frecuencia:** anual · **Referencia temporal:** 1 de enero
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `kpis_demograficos`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1971–2025
- **Rango válido:** [0, 100] · **Lectura:** mayor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** demografia

### contexto · Esperanza de vida al nacimiento (`esperanza_vida_nacimiento`)

Años que viviría en promedio una persona recién nacida con la mortalidad por edad del año.

- **Fórmula:** publicado por el INE (tablas de mortalidad), no recalculado
- **Unidad:** anos · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `stg_poblacion_anual (tabla 1414)`
- **Desagregaciones:** territorio, sexo · **Cobertura observada esperada:** 1975–2024
- **Rango válido:** [60, 100] · **Lectura:** neutro · **OKR:** O2 · **Pestaña del tablero:** demografia

### contexto · Esperanza de vida a los 65 años (`esperanza_vida_65`)

Años que quedan por vivir en promedio a los 65; aproxima la duración media de una pensión de jubilación.

- **Fórmula:** publicado por el INE (tablas de mortalidad), no recalculado
- **Unidad:** anos · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `stg_poblacion_anual (tabla 1415)`
- **Desagregaciones:** territorio, sexo · **Cobertura observada esperada:** 1975–2024
- **Rango válido:** [10, 35] · **Lectura:** mayor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** cotizacion_pensiones

### contexto · Afiliados por cada 100 personas de 16 a 64 años (`tasa_afiliacion_16_64`)

Relaciona la base de cotizantes con la población en edad de trabajar. No es una tasa de empleo (incluye pluriempleo y afiliados fuera de 16-64).

- **Fórmula:** afiliados en alta a 31/12 del año t / poblacion(16-64) a 1/1 del año t+1 × 100
- **Unidad:** porcentaje · **Frecuencia:** anual · **Referencia temporal:** 31 de diciembre
- **Fuente:** Cálculo del pipeline a partir de fuentes oficiales de distinto organismo · **Origen en el pipeline:** `kpis_integrados_anual`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1985–2024
- **Rango válido:** [0, 150] · **Lectura:** menor_es_mas_riesgo · **OKR:** O2 · **Pestaña del tablero:** cotizacion_pensiones

### contexto · Pensión contributiva media mensual (`pension_media_mensual`)

Importe medio por pensión contributiva en vigor en diciembre (nómina ordinaria, sin pagas extraordinarias).

- **Fórmula:** importe de la nómina mensual (miles EUR) × 1000 / número de pensiones
- **Unidad:** eur_mes · **Frecuencia:** anual · **Referencia temporal:** diciembre
- **Fuente:** Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) · **Origen en el pipeline:** `kpi_ratio_sostenibilidad_anual`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 2016–2025
- **Rango válido:** [100, 5000] · **Lectura:** neutro · **OKR:** O2 · **Pestaña del tablero:** sostenibilidad_financiera

### metrica_base · Población residente a 1 de enero (`poblacion`)

Stock de población; numerador y denominador de los KPIs de estructura.

- **Fórmula:** suma de la población por edad simple (Estadística Continua de Población)
- **Unidad:** personas · **Frecuencia:** anual · **Referencia temporal:** 1 de enero
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `stg_poblacion_anual (tabla 56934)`
- **Desagregaciones:** territorio, sexo, grupo_edad · **Cobertura observada esperada:** 1971–2025
- **Rango válido:** [0, 100000000] · **Lectura:** neutro · **OKR:** O1 · **Pestaña del tablero:** demografia

### metrica_base · Nacimientos (`nacimientos`)

Nacidos vivos de madre residente en España.

- **Fórmula:** publicado por el INE (Movimiento Natural de la Población)
- **Unidad:** nacimientos · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `stg_poblacion_anual (tabla 6566)`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1992–2024
- **Rango válido:** [0, 2000000] · **Lectura:** neutro · **OKR:** O1 · **Pestaña del tablero:** demografia

### metrica_base · Defunciones (`defunciones`)

Defunciones de residentes en España.

- **Fórmula:** publicado por el INE (Movimiento Natural de la Población)
- **Unidad:** defunciones · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Instituto Nacional de Estadística (INE) · **Origen en el pipeline:** `stg_poblacion_anual (tabla 6566)`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1992–2024
- **Rango válido:** [0, 2000000] · **Lectura:** neutro · **OKR:** O1 · **Pestaña del tablero:** demografia

### metrica_base · Afiliados en alta a la Seguridad Social (31 de diciembre) (`total_afiliados`)

Numerador del ratio afiliados/pensión. Cuenta situaciones de alta (una persona puede tener varias).

- **Fórmula:** afiliados en alta laboral el último día de diciembre (TOTAL SISTEMA)
- **Unidad:** afiliados · **Frecuencia:** anual · **Referencia temporal:** 31 de diciembre
- **Fuente:** Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) · **Origen en el pipeline:** `stg_afiliados_mensual`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1985–2025
- **Rango válido:** [0, 40000000] · **Lectura:** neutro · **OKR:** O1 · **Pestaña del tablero:** cotizacion_pensiones

### metrica_base · Pensiones contributivas en vigor (1 de diciembre) (`total_pensiones`)

Denominador del ratio afiliados/pensión.

- **Fórmula:** suma de pensiones de incapacidad permanente, jubilación, viudedad, orfandad y favor familiar
- **Unidad:** pensiones · **Frecuencia:** anual · **Referencia temporal:** diciembre
- **Fuente:** Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) · **Origen en el pipeline:** `kpi_ratio_sostenibilidad_anual`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 2016–2025
- **Rango válido:** [0, 20000000] · **Lectura:** neutro · **OKR:** O1 · **Pestaña del tablero:** cotizacion_pensiones

### metrica_base · Importe mensual de la nómina de pensiones contributivas (`importe_nomina_pensiones`)

Gasto mensual en nómina ordinaria; no es el gasto anual (excluye pagas extraordinarias y atrasos).

- **Fórmula:** importe de la nómina mensual de diciembre (TOTAL), publicado por el INSS
- **Unidad:** miles_eur · **Frecuencia:** anual · **Referencia temporal:** diciembre
- **Fuente:** Ministerio de Inclusión, Seguridad Social y Migraciones (TGSS e INSS) · **Origen en el pipeline:** `kpi_ratio_sostenibilidad_anual`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 2016–2025
- **Rango válido:** [0, 100000000] · **Lectura:** neutro · **OKR:** O1 · **Pestaña del tablero:** sostenibilidad_financiera

### metrica_base · Producto interior bruto a precios corrientes (`pib`)

Denominador de gasto_pensiones_pib. Los últimos años son provisionales.

- **Fórmula:** B1GQ a precios de mercado, precios corrientes (SEC 2010)
- **Unidad:** millones_eur · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Eurostat (Oficina Estadística de la Unión Europea) · **Origen en el pipeline:** `stg_macro_anual (nama_10_gdp)`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1995–2025
- **Rango válido:** [100000, 10000000] · **Lectura:** neutro · **OKR:** O1 · **Pestaña del tablero:** sostenibilidad_financiera

### metrica_base · Gasto en pensiones (ESSPROS) (`gasto_pensiones`)

Numerador de gasto_pensiones_pib. Incluye pensiones contributivas, no contributivas y de clases pasivas.

- **Fórmula:** gasto total en pensiones del Sistema Europeo de Estadísticas Integradas de Protección Social
- **Unidad:** millones_eur · **Frecuencia:** anual · **Referencia temporal:** año natural
- **Fuente:** Eurostat (Oficina Estadística de la Unión Europea) · **Origen en el pipeline:** `stg_macro_anual (spr_exp_pens)`
- **Desagregaciones:** territorio · **Cobertura observada esperada:** 1990–2024
- **Rango válido:** [1000, 1000000] · **Lectura:** neutro · **OKR:** O1 · **Pestaña del tablero:** sostenibilidad_financiera

