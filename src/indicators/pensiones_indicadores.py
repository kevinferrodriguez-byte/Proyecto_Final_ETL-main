from datetime import datetime, timezone
from pathlib import Path
import hashlib

from src.utils.silver_reader import SilverReader
from src.logger import get_logger
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.quality.seguridad_social_kpi_quality import SeguridadSocialKpiQuality
from src.indicators.kpi_ratio import RatioCotizantesPensionistas
from src.transform.seguridad_social.seguridad_social_schema import AfiliadosSchema, ImporteSchema, PensionesSchema
from src.utils.dataset_writer import DatasetWriter
from src.utils.run_manifest import RunManifest

LAYER = "Oro indicadores de pensiones"
TOTALS = {"afiliados": ["total_afiliados"], "pensiones": ["total_pensiones"], "importe": ["importe_total"]}
INPUTS = ("afiliados", "pensiones", "importe")


class PensionesIndicadores:
    def __init__(self, config):
        silver_config = config["silver"]["seguridad_social"]
        kpi_config = config["indicadores"]["pensiones"]
        self.dataset_name = kpi_config["dataset_name"]
        self.readers = {name: SilverReader(silver_config["manifests_path"], silver_config[name]["dataset_name"]) for name in INPUTS}
        self.input_schemas = {"afiliados": AfiliadosSchema(), "pensiones": PensionesSchema(), "importe": ImporteSchema()}
        self.ratio = RatioCotizantesPensionistas(kpi_config, config["sources"]["seguridad_social"]["name"])
        self.quality = SeguridadSocialKpiQuality(kpi_config, config["quality"])
        self.writer = DatasetWriter(config["output"], config["indicadores"]["output_path"])
        self.manifest = RunManifest(kpi_config["manifests_path"])
        self.report = QualityReport(kpi_config["manifests_path"], LAYER)
        self.logger = get_logger(__name__)

    def run(self):
        started_at = datetime.now(timezone.utc)
        run_id = f"indicadores_pensiones_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
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
        silver_run_ids = sorted({silver["run_id"] for silver in inputs.values()})
        if len(silver_run_ids) != 1:
            raise ValueError(f"Afiliados y pensiones proceden de ejecuciones de Plata distintas ({silver_run_ids}) (afiliados, pensiones e importe); vuelva a ejecutar Plata.")
        silver_run_id = silver_run_ids[0]
        evaluation.metrics["silver_run_id"] = silver_run_id
        if not evaluation.check("entrada_plata", "QLT-001: las entradas de Plata cumplen su esquema y no tienen totales nulos", self._input_problems(inputs)):
            raise ValueError(evaluation.rejection(LAYER))
        computed = self.ratio.compute(inputs["afiliados"]["frame"], inputs["pensiones"]["frame"], silver_run_id, started_at, inputs["importe"]["frame"])
        if not self.quality.evaluate(computed, evaluation).passed():
            raise ValueError(evaluation.rejection(LAYER))
        frame = computed["frame"]
        output_path = Path(self.writer.write(frame, self.ratio.schema, self.dataset_name))
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, inputs, silver_run_id, output_path, frame))
        self.logger.detail(f"{LAYER}: {len(frame)} años; manifiesto {manifest_path}")
        return {
            "run_id": run_id,
            "silver_run_id": silver_run_id,
            "bronze_run_ids": inputs["afiliados"]["bronze_run_ids"],
            "path": str(output_path),
            "manifest_path": manifest_path,
            "rows": len(frame),
            "frame": frame,
        }

    def _input_problems(self, inputs):
        problems = []
        for name, silver in inputs.items():
            frame = silver["frame"]
            problems.extend(self.input_schemas[name].problems(frame))
            if not problems:
                missing = int(frame[TOTALS[name]].isna().any(axis=1).sum())
                if missing:
                    problems.append(f"{missing} filas de {name} sin total")
        return problems

    def _manifest(self, run_id, started_at, inputs, silver_run_id, output_path, frame):
        with output_path.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
        return {
            "run_id": run_id,
            "dataset": self.dataset_name,
            "status": "completada",
            "nota": "Capa de indicadores de Oro: ratio afiliados/pensión y pensión media (stock de diciembre).",
            "started_at_utc": self._iso(started_at),
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "quality_report": f"{run_id}.quality.json",
            "silver_run_id": silver_run_id,
            "bronze_run_ids": inputs["afiliados"]["bronze_run_ids"],
            "silver_inputs": [
                {"dataset": name, "manifest": silver["manifest"], "path": self.manifest.relative_path(silver["path"]), "sha256": silver["sha256"]}
                for name, silver in inputs.items()
            ],
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
