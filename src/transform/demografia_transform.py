from datetime import datetime, timezone
from pathlib import Path
import hashlib

import pandas as pd

from src.utils.run_manifest import RunManifest
from src.logger import get_logger
from src.quality.demografia_quality import DemografiaQuality
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.transform.age_partition import AgePartition
from src.transform.demografia_schema import DemografiaSchema
from src.transform.ine.ine_bronze_reader import IneBronzeReader
from src.transform.ine.ine_normalizer import IneNormalizer
from src.transform.poblacion_consolidator import PoblacionConsolidator
from src.utils.dataset_writer import DatasetWriter

SORT_ORDER = ["metrica", "tabla_id", "escenario", "sexo", "fecha_referencia", "es_control", "tipo_edad", "edad_min"]


class DemografiaTransform:
    def __init__(self, config):
        ine_config = config["sources"]["ine"]
        silver_config = config["silver"]
        self.table_ids = ine_config["enabled_tables"]
        self.dataset_name = silver_config["dataset_name"]
        self.reader = IneBronzeReader(ine_config["storage"])
        self.normalizer = IneNormalizer(ine_config, silver_config["ine"])
        self.consolidator = PoblacionConsolidator(ine_config, silver_config["ine"])
        self.partition = AgePartition(silver_config["ine"]["homologated_top_age"])
        self.quality = DemografiaQuality(silver_config["validation"], config["quality"]["max_null_percentage"])
        self.schema = DemografiaSchema()
        self.writer = DatasetWriter(config["output"], config["paths"]["silver"])
        self.manifest = RunManifest(silver_config["manifests_path"])
        self.report = QualityReport(silver_config["manifests_path"], "Plata")
        self.logger = get_logger(__name__)

    def run(self, bronze_integrity):
        started_at = datetime.now(timezone.utc)
        run_id = f"silver_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
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
            raise RuntimeError("La integridad de Bronce no está en verde; Plata no lee payloads sin verificar.")
        payloads = self.reader.latest_payloads(self.table_ids)
        normalized = pd.concat(
            [self.normalizer.normalize(payload, self.reader.read(payload)) for payload in payloads],
            ignore_index=True,
        )
        partitioned = self.partition.apply(self.consolidator.consolidate(normalized))
        frame = partitioned["frame"].sort_values(SORT_ORDER, ignore_index=True)
        if not self.quality.evaluate(frame, partitioned["homologation"], evaluation).passed():
            raise ValueError(evaluation.rejection("Plata"))
        output_path = Path(self.writer.write(frame, self.schema, self.dataset_name))
        summary = self._summary(frame)
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, payloads, output_path, frame, summary))
        self.logger.detail(f"Plata demográfica: {len(frame)} filas; manifiesto {manifest_path}")
        return {
            "run_id": run_id,
            "bronze_run_ids": sorted({payload["run_id"] for payload in payloads}),
            "path": str(output_path),
            "manifest_path": manifest_path,
            "rows": len(frame),
            "summary": summary,
        }

    def _summary(self, frame):
        grouped = frame.groupby(["tabla_id", "metrica", "escenario"], dropna=False)
        rows = grouped.agg(filas=("valor", "size"), filas_control=("es_control", "sum")).reset_index()
        rows["filas_control"] = rows["filas_control"].astype("int64")
        by_metric = frame.groupby(["metrica", "unidad"], dropna=False).size().rename("filas").reset_index()
        return {
            "por_tabla_metrica_escenario": rows.astype({"tabla_id": object, "metrica": object, "escenario": object}).to_dict("records"),
            "por_metrica_unidad": by_metric.astype({"metrica": object, "unidad": object}).to_dict("records"),
        }

    def _manifest(self, run_id, started_at, payloads, output_path, frame, summary):
        with output_path.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
        return {
            "run_id": run_id,
            "quality_report": f"{run_id}.quality.json",
            "dataset": self.dataset_name,
            "status": "completada",
            "started_at_utc": self._iso(started_at),
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "bronze_inputs": [
                {
                    "table_id": payload["table_id"],
                    "query": payload["query"],
                    "run_id": payload["run_id"],
                    "sha256": payload["sha256"],
                    "path": self.manifest.relative_path(payload["path"]),
                }
                for payload in payloads
            ],
            "bronze_run_ids": sorted({payload["run_id"] for payload in payloads}),
            "rows": len(frame),
            "rows_summary": summary,
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
