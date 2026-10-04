from datetime import datetime, timezone
from pathlib import Path
import hashlib

from src.utils.dataset_writer import DatasetWriter
from src.utils.silver_reader import SilverReader
from src.logger import get_logger
from src.quality.kpi_quality import KpiQuality
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.utils.run_manifest import RunManifest
from src.indicators.demografia_kpis import DemografiaKpis
from src.transform.demografia_schema import DemografiaSchema
from src.indicators.kpi_schema import KpiSchema

SORT_ORDER = ["indicador", "escenario_kr", "escenario", "anyo"]


class DemografiaIndicadores:
    def __init__(self, config):
        gold_config = config["indicadores"]["demografia"]
        self.layer = "Oro indicadores demográficos"
        self.dataset_name = gold_config["dataset_name"]
        self.reader = SilverReader(config["silver"]["manifests_path"], config["silver"]["dataset_name"])
        self.silver_schema = DemografiaSchema()
        self.kpis = DemografiaKpis(gold_config)
        self.quality = KpiQuality(gold_config, config["quality"]["max_null_percentage"])
        self.schema = KpiSchema()
        self.writer = DatasetWriter(config["output"], config["indicadores"]["output_path"])
        self.manifest = RunManifest(gold_config["manifests_path"])
        self.report = QualityReport(gold_config["manifests_path"], self.layer)
        self.logger = get_logger(__name__)

    def run(self):
        started_at = datetime.now(timezone.utc)
        run_id = f"indicadores_demografia_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
        evaluation = QualityEvaluation()
        try:
            result = self._build(run_id, started_at, evaluation)
        except (OSError, ValueError, RuntimeError) as error:
            self.report.write(run_id, evaluation, str(error))
            raise
        result["quality_report_path"] = self.report.write(run_id, evaluation, None)
        return result

    def _build(self, run_id, started_at, evaluation):
        silver = self.reader.latest()
        evaluation.metrics["silver_run_id"] = silver["run_id"]
        if not evaluation.check("entrada_plata", "QLT-001: la entrada de Plata cumple DemografiaSchema", self.silver_schema.problems(silver["frame"])):
            raise ValueError(evaluation.rejection(self.layer))
        computed = self.kpis.compute(silver["frame"], silver["run_id"], started_at)
        computed["frame"] = computed["frame"].sort_values(SORT_ORDER, ignore_index=True)
        if not self.quality.evaluate(computed, evaluation).passed():
            raise ValueError(evaluation.rejection(self.layer))
        frame = computed["frame"]
        output_path = Path(self.writer.write(frame, self.schema, self.dataset_name))
        summary = self._summary(frame)
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, silver, output_path, frame, summary))
        self.logger.detail(f"{self.layer}: {len(frame)} KPIs; manifiesto {manifest_path}")
        return {
            "run_id": run_id,
            "silver_run_id": silver["run_id"],
            "bronze_run_ids": silver["bronze_run_ids"],
            "path": str(output_path),
            "manifest_path": manifest_path,
            "rows": len(frame),
            "summary": summary,
        }

    def _summary(self, frame):
        rows = frame.groupby(["indicador", "escenario_kr", "escenario"]).size().rename("filas").reset_index()
        return rows.astype({"indicador": object, "escenario_kr": object, "escenario": object}).to_dict("records")

    def _manifest(self, run_id, started_at, silver, output_path, frame, summary):
        with output_path.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
        return {
            "run_id": run_id,
            "dataset": self.dataset_name,
            "status": "completada",
            "started_at_utc": self._iso(started_at),
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "quality_report": f"{run_id}.quality.json",
            "silver_run_id": silver["run_id"],
            "bronze_run_ids": silver["bronze_run_ids"],
            "silver_input": {
                "manifest": silver["manifest"],
                "path": self.manifest.relative_path(silver["path"]),
                "sha256": silver["sha256"],
            },
            "rows": len(frame),
            "rows_by_indicator_and_scenario": summary,
            "payloads": [
                {
                    "dataset": self.dataset_name,
                    "path": self.manifest.relative_path(output_path),
                    "sha256": sha256,
                    "size_bytes": output_path.stat().st_size,
                    "rows": len(frame),
                }
            ],
        }

    def _iso(self, moment):
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
