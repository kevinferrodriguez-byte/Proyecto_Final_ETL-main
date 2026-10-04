# 12. Limitaciones y próximos pasos

## 12.1 Limitaciones de los datos

| Limitación | Efecto | Cómo se gestiona |
| --- | --- | --- |
| El KPI-07 mide **afiliados por pensión**, no cotizantes por pensionista. | Es menor que el ratio por pensionista que cita el documento (2,08 frente a unos 2,37). | Nombre y definición explícitos en `dim_indicador`; no se estiman pensionistas. |
| La serie anual de pensiones del avance mensual empieza en **2016**. | KPI-07 y pensión media solo cubren 2016-2025. | Cobertura declarada en el catálogo. Ampliarla requiere otras publicaciones del INSS (series históricas) no automatizadas en el MVP. |
| **Ruptura del saldo migratorio en 2021** (tablas 24309 y 69758, con unidades distintas). | 2008-2020 y 2021-2024 no son estrictamente comparables. | `metodologia` y `unidad` por fila; atípico registrado en 2022. |
| El PIB de 2023-2025 es **provisional** y el gasto ESSPROS se revisa. | Los KPI-08 más recientes pueden cambiar. | `estado_dato = provisional`; `tiene_datos_provisionales` en el panel. |
| La **afiliación cuenta situaciones de alta**, no personas. | La tasa de afiliación no es una tasa de empleo. | Advertencia en la definición del indicador. |
| El **importe de la nómina** es mensual. | No equivale al gasto anual del INSS (sin pagas extraordinarias). | Solo se usa para la pensión media; el gasto anual procede de Eurostat. |
| **Solo ámbito nacional.** | No hay análisis regional (pregunta territorial del Avance 1). | `dim_territorio` admite CCAA con claves nuevas; ver 12.3. |
| Las **proyecciones** son escenarios condicionales del INE (edición 2026-2076). | No son predicciones; difieren de la edición 2024-2074 citada en el documento. | Capa separada; `dim_escenario.alcance`. |
| La población histórica del INE tiene **redondeo por celda**. | Hombres + mujeres difieren del total en ≤ 12 personas por año antes de 2013. | Tolerancia documentada de 16 personas. |

## 12.2 Limitaciones técnicas

- **PostgreSQL:** los scripts se generan pero no se ejecutaron contra un servidor. La base verificada es SQLite.
- **Archivos abiertos en Windows / OneDrive:** la base SQLite se publica con la API de *backup* de SQLite, así que se actualiza aunque Power BI, DB Browser o el notebook la tengan abierta. Los CSV se reemplazan con reintentos. Si un archivo sigue bloqueado (por ejemplo, un CSV abierto en Excel), la carga se detiene con un mensaje que indica cómo resolverlo (`python main.py --desde carga`).
- **URL de la Seguridad Social:** cambian con cada publicación mensual y hay que actualizarlas en la configuración. Si la URL devuelve HTML, el extractor lo detecta y no guarda nada.
- **Coberturas esperadas del catálogo:** se actualizan a mano cuando las fuentes publican un año nuevo. Si no se actualizan, el año nuevo se integra igual y figura como `fuera_de_cobertura` en el reporte.
- **Duración de la ejecución:** una ejecución completa tarda unos 80 s, de los que unos 70 corresponden a la descarga de las proyecciones del INE.
- **Programación con `schedule`:** la librería vive dentro del proceso de Python; si `programar.py` se cierra o el equipo se apaga, no hay ejecuciones. En producción conviene arrancarlo con el sistema (Programador de tareas de Windows, `cron @reboot` o un servicio). Cada ejecución completa añade unos 20 MB a Bronce, que nunca se sobrescribe.

## 12.3 Próximos pasos

1. **Tablero de Power BI** (KR 2.2) sobre la capa Oro, siguiendo [11](11_guia_power_bi.md).
2. **Informe ejecutivo reproducible** (KR 3.2) a partir del notebook de validación.
3. **Desagregación por comunidad autónoma.**
   - El INE publica ICF, esperanza de vida (tablas 1441, 1448 y 1449) y población por CCAA.
   - La Seguridad Social publica afiliados y pensiones por provincia.
   - Basta con ampliar los filtros, el catálogo `modelo.territories` y los mapeos.
4. **Capa de escenarios fiscales oficiales**, si se decide incorporarla: proyecciones de gasto del Ageing Report de la Comisión Europea o de la AIReF como nuevos escenarios en `dim_escenario`, **sin mezclarlos con los demográficos** y sin modelación propia.
5. **Banco de España** para variables de contexto que hoy no usa ningún KPI (IPC para la revalorización, deuda pública).
6. **Modelación (fuera del ETL):** estimar el efecto de la migración o de la jubilación del *baby boom* sobre el balance del sistema exige supuestos de empleo, productividad y cotización (retroalimentación R4). Sería un proyecto analítico aparte que consumiría esta base.
7. **Alertas** cuando una ejecución programada falle o una regla de calidad no se cumpla (la programación ya está implementada con `schedule` en `programar.py`; hoy el resultado queda en `logs/programacion.jsonl`).
