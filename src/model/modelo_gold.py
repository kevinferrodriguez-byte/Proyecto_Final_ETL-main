from datetime import datetime, timezone
from pathlib import Path
import hashlib

from src.indicators.integrados_schema import KpiIntegradoSchema
from src.indicators.kpi_ratio_schema import KpiRatioSchema
from src.indicators.kpi_schema import KpiSchema
from src.logger import get_logger
from src.model.dimensiones import Dimensiones
from src.model.hechos import Hechos
from src.model.panel import Panel
from src.quality.modelo_quality import ModeloQuality
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.transform.demografia_schema import DemografiaSchema
from src.transform.eurostat.eurostat_schema import MacroSchema
from src.transform.seguridad_social.seguridad_social_schema import AfiliadosSchema
from src.utils.dataset_writer import DatasetWriter
from src.utils.run_manifest import RunManifest
from src.utils.silver_reader import SilverReader

LAYER = "Oro modelo"
DIMENSIONS = ("dim_tiempo", "dim_territorio", "dim_sexo", "dim_grupo_edad", "dim_fuente", "dim_indicador")
FACT = "fact_indicadores_anual"
PANEL = "dm_panel_anual"


class ModeloGold:
    """Oro · modelo dimensional (estrella) de datos observados para Power BI.

    Lee solo artefactos con manifiesto completado (sha256 verificado) de Plata y de la capa de indicadores,
    comprueba que proceden de las mismas ejecuciones (linaje coherente), construye dimensiones, hechos y el
    panel ancho, valida y escribe. Cualquier regla en `falla` detiene la escritura; las advertencias se registran.
    """

    def __init__(self, config):
        silver = config["silver"]
        social = silver["seguridad_social"]
        indicators = config["indicadores"]
        model = config["modelo"]
        self.readers = {
            "stg_poblacion_anual": SilverReader(silver["manifests_path"], silver["dataset_name"]),
            "stg_afiliados_mensual": SilverReader(social["manifests_path"], social["afiliados"]["dataset_name"]),
            "stg_macro_anual": SilverReader(silver["eurostat"]["manifests_path"], silver["eurostat"]["dataset_name"]),
            "kpis_demograficos": SilverReader(indicators["demografia"]["manifests_path"], indicators["demografia"]["dataset_name"]),
            "kpi_ratio_sostenibilidad_anual": SilverReader(indicators["pensiones"]["manifests_path"], indicators["pensiones"]["dataset_name"]),
            "kpis_integrados_anual": SilverReader(indicators["integrados"]["manifests_path"], indicators["integrados"]["dataset_name"]),
        }
        self.input_schemas = {
            "stg_poblacion_anual": DemografiaSchema(),
            "stg_afiliados_mensual": AfiliadosSchema(),
            "stg_macro_anual": MacroSchema(),
            "kpis_demograficos": KpiSchema(),
            "kpi_ratio_sostenibilidad_anual": KpiRatioSchema(),
            "kpis_integrados_anual": KpiIntegradoSchema(),
        }
        self.dimensions = Dimensiones(config)
        self.facts = Hechos(config)
        self.panel = Panel(config)
        self.quality = ModeloQuality(config)
        self.writer = DatasetWriter(config["output"], model["output_path"])
        self.manifest = RunManifest(model["manifests_path"])
        self.report = QualityReport(model["manifests_path"], LAYER)
        self.logger = get_logger(__name__)

    def run(self):
        started_at = datetime.now(timezone.utc)
        run_id = f"gold_modelo_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
        evaluation = QualityEvaluation()
        try:
            result = self._build(run_id, started_at, evaluation)
        except (OSError, ValueError, RuntimeError) as error:
            self.report.write(run_id, evaluation, str(error))
            raise
        result["quality_report_path"] = self.report.write(run_id, evaluation, None)
        return result

    def _build(self, run_id, started_at, evaluation):
        inputs = {name: reader.latest() for name, reader in self.readers.items()}
        evaluation.metrics["entradas"] = {name: source["run_id"] for name, source in inputs.items()}
        problems = [f"{name}: {problem}" for name, source in inputs.items() for problem in self.input_schemas[name].problems(source["frame"])]
        if not evaluation.check("entradas_esquema", "QLT-001: cada entrada cumple su esquema", problems):
            raise ValueError(evaluation.rejection(LAYER))
        if not evaluation.check("linaje_coherente", "MOD-00: los indicadores proceden de las mismas ejecuciones de Plata que se leen", self._lineage(inputs)):
            raise ValueError(evaluation.rejection(LAYER))
        integrated = self.facts.integrate(inputs)
        kpis = inputs["kpis_demograficos"]["frame"]
        projected_years = kpis.loc[kpis["estado_dato"].eq("proyectado"), "anyo"].unique()
        dimensions = self.dimensions.build(integrated["frame"], projected_years)
        fact = self.facts.assign_keys(integrated["frame"], dimensions, run_id, started_at)
        panel = self.panel.build(fact, dimensions, run_id)
        macro = inputs["stg_macro_anual"]["frame"]
        model = {
            "dimensions": dimensions,
            "fact": fact,
            "panel": panel,
            "schemas": {**self.dimensions.schemas, FACT: self.facts.schema, PANEL: self.panel.schema},
            "expected_rows": integrated["rows_by_part"],
            "control_population": macro[macro["metrica"].eq("poblacion_1_enero")][["anyo", "valor"]],
        }
        if not self.quality.evaluate(model, evaluation).passed():
            raise ValueError(evaluation.rejection(LAYER))
        outputs = self._write(model)
        summary = self._summary(fact, dimensions, evaluation)
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, inputs, outputs, summary))
        self.logger.detail(f"{LAYER}: {len(fact)} hechos; manifiesto {manifest_path}")
        return {
            "run_id": run_id,
            "input_run_ids": evaluation.metrics["entradas"],
            "paths": {name: str(path) for name, (path, _) in outputs.items()},
            "manifest_path": manifest_path,
            "rows": {name: rows for name, (_, rows) in outputs.items()},
            "summary": summary,
        }

    def _lineage(self, inputs):
        problems = []
        kpi_silver = sorted(inputs["kpis_demograficos"]["frame"]["silver_run_id"].unique())
        if kpi_silver != [inputs["stg_poblacion_anual"]["run_id"]]:
            problems.append(f"kpis_demograficos procede de Plata {kpi_silver} y la Plata INE leída es {inputs['stg_poblacion_anual']['run_id']}")
        ratio_silver = sorted(inputs["kpi_ratio_sostenibilidad_anual"]["frame"]["silver_run_id"].unique())
        if ratio_silver != [inputs["stg_afiliados_mensual"]["run_id"]]:
            problems.append(f"kpi_ratio_sostenibilidad_anual procede de Plata {ratio_silver} y la Plata de Seguridad Social leída es {inputs['stg_afiliados_mensual']['run_id']}")
        origins = " ".join(inputs["kpis_integrados_anual"]["frame"]["run_ids_origen"].unique())
        for name in ("stg_macro_anual", "stg_afiliados_mensual", "stg_poblacion_anual"):
            if inputs[name]["run_id"] not in origins:
                problems.append(f"kpis_integrados_anual no procede de la ejecución de {name} leída ({inputs[name]['run_id']})")
        if problems:
            problems.append("vuelva a ejecutar desde la etapa indicadores")
        return problems

    def _write(self, model):
        outputs = {}
        for name in DIMENSIONS:
            outputs[name] = (Path(self.writer.write(model["dimensions"][name], model["schemas"][name], name)), len(model["dimensions"][name]))
        outputs[FACT] = (Path(self.writer.write(model["fact"], model["schemas"][FACT], FACT)), len(model["fact"]))
        outputs[PANEL] = (Path(self.writer.write(model["panel"], model["schemas"][PANEL], PANEL)), len(model["panel"]))
        return outputs

    def _summary(self, fact, dimensions, evaluation):
        counts = fact.merge(dimensions["dim_indicador"][["indicador_key", "codigo_indicador", "tipo_indicador"]], on="indicador_key")
        by_indicator = counts.groupby(["tipo_indicador", "codigo_indicador"]).size().rename("filas").reset_index()
        warnings = [rule for rule in evaluation.rules if rule["resultado"] == "advertencia"]
        return {
            "anyos_observados": [int(fact["tiempo_key"].min()), int(fact["tiempo_key"].max())],
            "indicadores": by_indicator.astype({"tipo_indicador": object, "codigo_indicador": object}).to_dict("records"),
            "completitud_temporal_minima": evaluation.metrics.get("completitud_temporal_minima"),
            "completitud_temporal_media": evaluation.metrics.get("completitud_temporal_media"),
            "advertencias": sum(len(rule["detalle"]) for rule in warnings),
        }

    def _manifest(self, run_id, started_at, inputs, outputs, summary):
        payloads = []
        for name, (path, rows) in outputs.items():
            with path.open("rb") as file:
                sha256 = hashlib.file_digest(file, "sha256").hexdigest()
            payloads.append({"dataset": name, "path": self.manifest.relative_path(path), "sha256": sha256, "size_bytes": path.stat().st_size, "rows": rows})
        return {
            "run_id": run_id,
            "dataset": FACT,
            "status": "completada",
            "started_at_utc": self._iso(started_at),
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "quality_report": f"{run_id}.quality.json",
            "inputs": [
                {"dataset": name, "run_id": source["run_id"], "manifest": source["manifest"], "path": self.manifest.relative_path(source["path"]), "sha256": source["sha256"]}
                for name, source in inputs.items()
            ],
            "bronze_run_ids": sorted({run for source in inputs.values() for run in source["bronze_run_ids"]}),
            "resumen": summary,
            "payloads": payloads,
        }

    def _iso(self, moment):
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
