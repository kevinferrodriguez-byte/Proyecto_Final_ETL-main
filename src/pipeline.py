"""Orquestación del pipeline ETL con arquitectura Medallion.

Fuentes → Bronce → Plata → Oro (indicadores → modelo → escenarios) → carga (SQLite, CSV y scripts PostgreSQL).

Cada paso es independiente, lee solo artefactos con manifiesto completado de la capa anterior y registra
sus `run_id` en el registro de ejecución (`logs/ejecuciones/pipeline_{UTC}.json`), que se escribe también
cuando la ejecución falla.
"""

from pathlib import Path

from src.extract.bronze_integrity import BronzeIntegrityChecker, PROBLEM_KEYS
from src.extract.eurostat.eurostat_extractor import EurostatExtractor
from src.extract.ine.ine_extractor import IneExtractor
from src.extract.seguridad_social.seguridad_social_extractor import SeguridadSocialExtractor
from src.indicators.demografia_indicadores import DemografiaIndicadores
from src.indicators.integrados_indicadores import IntegradosIndicadores
from src.indicators.pensiones_indicadores import PensionesIndicadores
from src.logger import configure_logging, get_logger
from src.model.modelo_gold import ModeloGold
from src.scenarios.escenarios_gold import EscenariosGold
from src.serving.carga import Carga
from src.transform.demografia_transform import DemografiaTransform
from src.transform.eurostat.eurostat_transform import EurostatTransform
from src.transform.seguridad_social.seguridad_social_transform import SeguridadSocialTransform
from src.utils.pipeline_run_log import PipelineRunLog

STAGES = ("bronce", "plata", "indicadores", "modelo", "escenarios", "carga")
SOURCES = ("ine", "seguridad_social", "eurostat")
STEPS = (
    ("bronce_ine", "bronce", "Bronce · descarga de las tablas del INE (API JSON)"),
    ("bronce_seguridad_social", "bronce", "Bronce · descarga de los libros de la Seguridad Social (XLSX)"),
    ("bronce_eurostat", "bronce", "Bronce · descarga de los conjuntos de Eurostat (JSON-stat)"),
    ("integridad_bronce", "plata", "Bronce · verificación de integridad payload-manifiesto de las tres fuentes"),
    ("plata_ine", "plata", "Plata · stg_poblacion_anual (INE)"),
    ("plata_seguridad_social", "plata", "Plata · stg_afiliados_mensual, stg_pensiones_cuantia y stg_pensiones_importe"),
    ("plata_eurostat", "plata", "Plata · stg_macro_anual (Eurostat)"),
    ("indicadores_demografia", "indicadores", "Oro/indicadores · kpis_demograficos"),
    ("indicadores_pensiones", "indicadores", "Oro/indicadores · kpi_ratio_sostenibilidad_anual"),
    ("indicadores_integrados", "indicadores", "Oro/indicadores · kpis_integrados_anual (gasto/PIB y afiliación)"),
    ("modelo", "modelo", "Oro/modelo · dimensiones, fact_indicadores_anual y dm_panel_anual"),
    ("escenarios", "escenarios", "Oro/escenarios · proyecciones oficiales del INE (capa separada)"),
    ("carga", "carga", "Carga · SQLite, CSV y scripts PostgreSQL para Power BI"),
)
STEP_STAGES = {name: stage for name, stage, _ in STEPS}
STEP_TITLES = {name: title for name, _, title in STEPS}


class Pipeline:
    def __init__(self, config):
        self.config = config
        configure_logging(config["logging"])
        self.logger = get_logger(__name__)
        self.integrity = None
        self.handlers = {
            "bronce_ine": self._bronze_ine,
            "bronce_seguridad_social": self._bronze_seguridad_social,
            "bronce_eurostat": self._bronze_eurostat,
            "integridad_bronce": self._integrity,
            "plata_ine": self._silver_ine,
            "plata_seguridad_social": self._silver_seguridad_social,
            "plata_eurostat": self._silver_eurostat,
            "indicadores_demografia": self._indicators_demografia,
            "indicadores_pensiones": self._indicators_pensiones,
            "indicadores_integrados": self._indicators_integrados,
            "modelo": self._model,
            "escenarios": self._scenarios,
            "carga": self._load,
        }

    def run(self, start_stage, end_stage=None):
        end_stage = end_stage or STAGES[-1]
        for stage in (start_stage, end_stage):
            if stage not in STAGES:
                raise ValueError(f"La etapa '{stage}' no existe; use una de: {', '.join(STAGES)}.")
        if STAGES.index(end_stage) < STAGES.index(start_stage):
            raise ValueError(f"La etapa final '{end_stage}' es anterior a la inicial '{start_stage}'.")
        stages = STAGES[STAGES.index(start_stage) : STAGES.index(end_stage) + 1]
        steps = [name for name, stage, _ in STEPS if stage in stages]
        self._prepare_directories()
        run_log = PipelineRunLog(self.config["pipeline"]["runs_path"], start_stage, stages)
        self.logger.start(f"Pipeline {run_log.run_id} · etapas {stages[0]} → {stages[-1]} · {len(steps)} pasos")
        results = {"run_id": run_log.run_id}
        self.integrity = None
        try:
            for position, step in enumerate(steps, start=1):
                self.logger.step(f"{position}/{len(steps)} · {STEP_TITLES[step]}")
                run_log.start(step)
                result = self.handlers[step]()
                results[step] = result
                run_log.link(step, result.get("run_id"))
                run_log.finish(self._details(result))
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            failed_step = run_log.current["etapa"] if run_log.current else "preparación"
            self.logger.error(f"Paso {failed_step} interrumpido: {error}")
            run_log.fail(error)
            record_path = Path(run_log.write()).as_posix()
            self.logger.end(f"Pipeline fallido en {run_log.record['duracion_s']:.0f} s · registro {record_path}")
            raise
        results["registro"] = run_log.write()
        self.logger.ok(f"Registro de ejecución: {Path(results['registro']).as_posix()}")
        self.logger.end(f"Pipeline completado en {run_log.record['duracion_s']:.0f} s")
        return results

    # ── Bronce ─────────────────────────────────────────────────────────────
    def _bronze_ine(self):
        config = self.config["sources"]["ine"]
        with IneExtractor(config) as extractor:
            bronze = extractor.extract_tables(config["enabled_tables"])
        return self._bronze_result(bronze)

    def _bronze_seguridad_social(self):
        config = self.config["sources"]["seguridad_social"]
        with SeguridadSocialExtractor(config) as extractor:
            bronze = extractor.extract_files(config["enabled_files"])
        return self._bronze_result(bronze)

    def _bronze_eurostat(self):
        config = self.config["sources"]["eurostat"]
        with EurostatExtractor(config) as extractor:
            bronze = extractor.extract_datasets(config["enabled_datasets"])
        return self._bronze_result(bronze)

    def _bronze_result(self, bronze):
        self.logger.ok(f"Manifiesto de Bronce {bronze['run_id']}: {len(bronze['records'])} archivos guardados sin modificar")
        return {"run_id": bronze["run_id"], "manifiesto": Path(bronze["manifest_path"]).as_posix(), "payloads": len(bronze["records"])}

    def _integrity(self):
        reports = {}
        for source in SOURCES:
            storage = self.config["sources"][source]["storage"]
            report = BronzeIntegrityChecker(storage["payloads_path"], storage["manifests_path"], [storage["unmanifested_path"]]).check()
            if not report["ok"]:
                for problem in PROBLEM_KEYS:
                    for item in report[problem]:
                        self.logger.detail(f"Integridad de Bronce {source} | {problem}: {item}")
                raise RuntimeError(
                    f"La verificación de integridad de Bronce {source} falló: "
                    + ", ".join(f"{problem}={len(report[problem])}" for problem in PROBLEM_KEYS)
                    + ". Revise el registro de ejecución antes de promover datos a Plata."
                )
            self.logger.ok(f"{source}: {report['payloads_checked']} archivos coinciden con sus {report['manifests_checked']} manifiestos (sin huérfanos ni diferencias)")
            reports[source] = report
        self.integrity = reports
        return {"payloads_verificados": {source: report["payloads_checked"] for source, report in reports.items()}}

    def _integrity_of(self, source):
        if self.integrity is None:
            raise RuntimeError("Plata requiere la verificación de integridad de Bronce en la misma ejecución.")
        return self.integrity[source]

    # ── Plata ──────────────────────────────────────────────────────────────
    def _silver_ine(self):
        silver = DemografiaTransform(self.config).run(self._integrity_of("ine"))
        rows_by_metric = {}
        for row in silver["summary"]["por_metrica_unidad"]:
            rows_by_metric[row["metrica"]] = rows_by_metric.get(row["metrica"], 0) + row["filas"]
        self.logger.ok(f"{self._number(silver['rows'])} filas en {Path(silver['path']).as_posix()}")
        self.logger.ok("Filas por métrica: " + " · ".join(f"{metric} {self._number(rows)}" for metric, rows in rows_by_metric.items()))
        return self._layer_result(silver)

    def _silver_seguridad_social(self):
        silver = SeguridadSocialTransform(self.config).run(self._integrity_of("seguridad_social"))
        for name, path in silver["paths"].items():
            summary = silver["summary"][name]
            self.logger.ok(f"{self._number(summary['filas'])} filas en {Path(path).as_posix()} ({summary['desde']} a {summary['hasta']})")
        return self._layer_result(silver)

    def _silver_eurostat(self):
        silver = EurostatTransform(self.config).run(self._integrity_of("eurostat"))
        self.logger.ok(f"{self._number(silver['rows'])} filas en {Path(silver['path']).as_posix()}")
        self.logger.ok("Métricas: " + " · ".join(f"{metric} {item['desde']}–{item['hasta']}" for metric, item in silver["summary"].items()))
        return self._layer_result(silver)

    # ── Oro: indicadores ───────────────────────────────────────────────────
    def _indicators_demografia(self):
        gold = DemografiaIndicadores(self.config).run()
        indicators = sorted({row["indicador"] for row in gold["summary"]})
        self.logger.ok(f"{self._number(gold['rows'])} KPIs en {Path(gold['path']).as_posix()} ({', '.join(indicators)})")
        return self._layer_result(gold)

    def _indicators_pensiones(self):
        kpi = PensionesIndicadores(self.config).run()
        frame = kpi["frame"]
        latest = frame.iloc[-1]
        self.logger.ok(f"{kpi['rows']} años ({frame['anyo'].min()}–{frame['anyo'].max()}) en {Path(kpi['path']).as_posix()}")
        self.logger.ok(
            f"Diciembre de {latest['anyo']}: {latest['ratio_cotizantes_pensionistas']:.3f} afiliados por pensión · pensión media {latest['pension_media_eur']:.2f} EUR".replace(".", ",")
        )
        return self._layer_result(kpi)

    def _indicators_integrados(self):
        kpi = IntegradosIndicadores(self.config).run()
        for indicator, item in kpi["summary"].items():
            self.logger.ok(f"{indicator}: {item['filas']} años ({item['desde']}–{item['hasta']}), último valor {item['ultimo_valor']}")
        self.logger.ok(f"Diferencia máxima con el gasto/PIB publicado por Eurostat: {kpi['published_difference_pp']} pp")
        return self._layer_result(kpi)

    # ── Oro: modelo, escenarios y carga ────────────────────────────────────
    def _model(self):
        model = ModeloGold(self.config).run()
        rows = model["rows"]
        self.logger.ok("Dimensiones: " + " · ".join(f"{name} {self._number(rows[name])}" for name in rows if name.startswith("dim_")))
        self.logger.ok(f"fact_indicadores_anual: {self._number(rows['fact_indicadores_anual'])} hechos · dm_panel_anual: {rows['dm_panel_anual']} años")
        if model["summary"]["advertencias"]:
            self.logger.warn(f"{model['summary']['advertencias']} advertencias de calidad (atípicos o consistencia entre fuentes); detalle en el reporte")
        return self._layer_result(model)

    def _scenarios(self):
        scenarios = EscenariosGold(self.config).run()
        rows = scenarios["rows"]
        self.logger.ok(f"fact_proyecciones_demograficas: {self._number(rows['fact_proyecciones_demograficas'])} filas · dm_escenarios_2050: {self._number(rows['dm_escenarios_2050'])} filas")
        return self._layer_result(scenarios)

    def _load(self):
        load = Carga(self.config).run()
        self.logger.ok(f"SQLite: {Path(load['sqlite_path']).as_posix()} ({load['tables']} tablas, {load['views']} vistas, integridad referencial verificada)")
        self.logger.ok(f"CSV para Power BI: {Path(load['csv_dir']).as_posix()} · scripts PostgreSQL: {Path(load['postgresql_dir']).as_posix()}")
        return self._layer_result(load)

    # ── utilidades ─────────────────────────────────────────────────────────
    def _layer_result(self, result):
        keys = ("run_id", "manifest_path", "quality_report_path", "rows", "path", "paths", "input_run_ids", "silver_run_id", "bronze_run_ids")
        return {key: result[key] for key in keys if key in result}

    def _details(self, result):
        details = {}
        for key, value in result.items():
            if key in ("manifest_path", "quality_report_path", "path"):
                value = Path(value).as_posix()
            elif key == "paths":
                value = {name: Path(path).as_posix() for name, path in value.items()}
            details[{"manifest_path": "manifiesto", "quality_report_path": "reporte_calidad", "rows": "filas"}.get(key, key)] = value
        return details

    def _prepare_directories(self):
        for key in ("bronze", "silver", "gold", "logs"):
            Path(self.config["paths"][key]).mkdir(parents=True, exist_ok=True)
        Path(self.config["pipeline"]["runs_path"]).mkdir(parents=True, exist_ok=True)

    def _number(self, value):
        return f"{value:,}".replace(",", " ")
