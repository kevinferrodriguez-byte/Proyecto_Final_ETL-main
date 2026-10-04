from datetime import datetime, timezone
from pathlib import Path
import hashlib

import pandas as pd

from src.logger import get_logger
from src.quality.eurostat_quality import EurostatQuality
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.transform.eurostat.eurostat_bronze_reader import EurostatBronzeReader
from src.transform.eurostat.eurostat_normalizer import EurostatNormalizer
from src.transform.eurostat.eurostat_schema import MacroSchema
from src.transform.eurostat.jsonstat_parser import JsonStatParser
from src.utils.dataset_writer import DatasetWriter
from src.utils.run_manifest import RunManifest

LAYER = "Plata Eurostat"
SORT_ORDER = ["dataset_id", "metrica", "territorio", "anyo"]


class EurostatTransform:
    """Bronce Eurostat (JSON-stat) -> Plata `stg_macro_anual` (formato largo, tipado y validado)."""

    def __init__(self, config):
        source_config = config["sources"]["eurostat"]
        silver_config = config["silver"]["eurostat"]
        self.dataset_ids = source_config["enabled_datasets"]
        self.dataset_name = silver_config["dataset_name"]
        self.reader = EurostatBronzeReader(source_config["storage"])
        self.parser = JsonStatParser()
        self.normalizer = EurostatNormalizer(source_config)
        self.quality = EurostatQuality(source_config, config["quality"])
        self.schema = MacroSchema()
        self.writer = DatasetWriter(config["output"], silver_config["output_path"])
        self.manifest = RunManifest(silver_config["manifests_path"])
        self.report = QualityReport(silver_config["manifests_path"], LAYER)
        self.logger = get_logger(__name__)

    def run(self, bronze_integrity):
        started_at = datetime.now(timezone.utc)
        run_id = f"silver_eurostat_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
        evaluation = QualityEvaluation()
        try:
            result = self._build(run_id, started_at, bronze_integrity, evaluation)
        except (OSError, ValueError, RuntimeError) as error:
            self.report.write(run_id, evaluation, str(error))
            raise
        result["quality_report_path"] = self.report.write(run_id, evaluation, None)
        return result

    def _build(self, run_id, started_at, bronze_integrity, evaluation):
        integrity_problems = [] if bronze_integrity["ok"] else ["la verificación de integridad de Bronce no está en verde"]
        if not evaluation.check("integridad_bronce", "Plata solo lee Bronce con la integridad en verde", integrity_problems):
            raise RuntimeError("La integridad de Bronce de Eurostat no está en verde; Plata no lee payloads sin verificar.")
        payloads = self.reader.latest_payloads(self.dataset_ids)
        parsed = []
        rows_in = {}
        for dataset_id in self.dataset_ids:
            payload = payloads[dataset_id]
            raw = self.parser.parse(self.reader.read(payload))
            rows_in[dataset_id] = len(raw)
            parsed.append(self.normalizer.normalize(payload, raw))
        frame = pd.concat(parsed, ignore_index=True).sort_values(SORT_ORDER, ignore_index=True)
        evaluation.metrics["filas_entrada_por_conjunto"] = rows_in
        evaluation.metrics["filas_salida_por_conjunto"] = {str(key): int(value) for key, value in frame.groupby("dataset_id").size().items()}
        if not self.quality.evaluate(frame, evaluation, started_at.date()).passed():
            raise ValueError(evaluation.rejection(LAYER))
        output_path = Path(self.writer.write(frame, self.schema, self.dataset_name))
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, payloads, output_path, frame))
        self.logger.detail(f"{LAYER}: {len(frame)} filas; manifiesto {manifest_path}")
        return {
            "run_id": run_id,
            "bronze_run_ids": sorted({payload["run_id"] for payload in payloads.values()}),
            "path": str(output_path),
            "manifest_path": manifest_path,
            "rows": len(frame),
            "summary": {
                str(metric): {"filas": int(len(group)), "desde": int(group["anyo"].min()), "hasta": int(group["anyo"].max())}
                for metric, group in frame.groupby("metrica")
            },
        }

    def _manifest(self, run_id, started_at, payloads, output_path, frame):
        with output_path.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
        return {
            "run_id": run_id,
            "dataset": self.dataset_name,
            "status": "completada",
            "quality_report": f"{run_id}.quality.json",
            "started_at_utc": self._iso(started_at),
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "bronze_inputs": [
                {
                    "dataset_id": payload["dataset_id"],
                    "run_id": payload["run_id"],
                    "sha256": payload["sha256"],
                    "source_updated": payload["source_updated"],
                    "path": self.manifest.relative_path(payload["path"]),
                }
                for payload in payloads.values()
            ],
            "bronze_run_ids": sorted({payload["run_id"] for payload in payloads.values()}),
            "rows": len(frame),
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
