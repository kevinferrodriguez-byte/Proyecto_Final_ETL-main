from datetime import datetime, timezone
from pathlib import Path
import hashlib

from src.indicators.integrados import IndicadoresIntegrados
from src.logger import get_logger
from src.quality.integrados_quality import IntegradosQuality
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.transform.demografia_schema import DemografiaSchema
from src.transform.eurostat.eurostat_schema import MacroSchema
from src.transform.seguridad_social.seguridad_social_schema import AfiliadosSchema
from src.utils.dataset_writer import DatasetWriter
from src.utils.run_manifest import RunManifest
from src.utils.silver_reader import SilverReader

LAYER = "Oro indicadores integrados"


class IntegradosIndicadores:
    """Capa de indicadores: KPIs que cruzan fuentes (Eurostat, Seguridad Social e INE), leídos de Plata verificada."""

    def __init__(self, config):
        integrated = config["indicadores"]["integrados"]
        social = config["silver"]["seguridad_social"]
        self.dataset_name = integrated["dataset_name"]
        self.readers = {
            "macro": SilverReader(config["silver"]["eurostat"]["manifests_path"], config["silver"]["eurostat"]["dataset_name"]),
            "afiliados": SilverReader(social["manifests_path"], social["afiliados"]["dataset_name"]),
            "poblacion": SilverReader(config["silver"]["manifests_path"], config["silver"]["dataset_name"]),
        }
        self.input_schemas = {"macro": MacroSchema(), "afiliados": AfiliadosSchema(), "poblacion": DemografiaSchema()}
        self.indicators = IndicadoresIntegrados(config)
        self.quality = IntegradosQuality(config)
        self.writer = DatasetWriter(config["output"], config["indicadores"]["output_path"])
        self.manifest = RunManifest(integrated["manifests_path"])
        self.report = QualityReport(integrated["manifests_path"], LAYER)
        self.logger = get_logger(__name__)

    def run(self):
        started_at = datetime.now(timezone.utc)
        run_id = f"indicadores_integrados_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
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
        if not evaluation.check("entradas_esquema", "QLT-001: cada entrada de Plata cumple su esquema", problems):
            raise ValueError(evaluation.rejection(LAYER))
        frame = self.indicators.compute(inputs["macro"], inputs["afiliados"], inputs["poblacion"], started_at)
        if not self.quality.evaluate(frame, evaluation).passed():
            raise ValueError(evaluation.rejection(LAYER))
        output_path = Path(self.writer.write(frame, self.indicators.schema, self.dataset_name))
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, inputs, output_path, frame))
        summary = {
            str(indicator): {"filas": int(len(group)), "desde": int(group["anyo"].min()), "hasta": int(group["anyo"].max()), "ultimo_valor": round(float(group.sort_values("anyo")["valor"].iloc[-1]), 4)}
            for indicator, group in frame.groupby("indicador")
        }
        self.logger.detail(f"{LAYER}: {len(frame)} filas; manifiesto {manifest_path}")
        return {
            "run_id": run_id,
            "input_run_ids": evaluation.metrics["entradas"],
            "bronze_run_ids": sorted({run for source in inputs.values() for run in source["bronze_run_ids"]}),
            "path": str(output_path),
            "manifest_path": manifest_path,
            "rows": len(frame),
            "summary": summary,
            "published_difference_pp": evaluation.metrics.get("diferencia_publicado_max_pp"),
        }

    def _manifest(self, run_id, started_at, inputs, output_path, frame):
        with output_path.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
        return {
            "run_id": run_id,
            "dataset": self.dataset_name,
            "status": "completada",
            "started_at_utc": self._iso(started_at),
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "quality_report": f"{run_id}.quality.json",
            "silver_inputs": [
                {"dataset": name, "run_id": source["run_id"], "manifest": source["manifest"], "path": self.manifest.relative_path(source["path"]), "sha256": source["sha256"]}
                for name, source in inputs.items()
            ],
            "bronze_run_ids": sorted({run for source in inputs.values() for run in source["bronze_run_ids"]}),
            "rows": len(frame),
            "payloads": [
                {"dataset": self.dataset_name, "path": self.manifest.relative_path(output_path), "sha256": sha256, "size_bytes": output_path.stat().st_size, "rows": len(frame)}
            ],
        }

    def _iso(self, moment):
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
