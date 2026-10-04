from datetime import datetime, timezone
from pathlib import Path
import hashlib

from src.logger import get_logger
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.quality.seguridad_social_quality import SeguridadSocialQuality
from src.transform.seguridad_social.afiliados_parser import AfiliadosParser
from src.transform.seguridad_social.pensiones_parser import PensionesParser
from src.transform.seguridad_social.seguridad_social_bronze_reader import SeguridadSocialBronzeReader
from src.transform.seguridad_social.seguridad_social_schema import AfiliadosSchema, ImporteSchema, PensionesSchema
from src.utils.dataset_writer import DatasetWriter
from src.utils.run_manifest import RunManifest

LAYER = "Plata Seguridad Social"
SORT_ORDER = {"afiliados": ["territorio", "anyo", "mes"], "pensiones": ["territorio", "tipo_corte", "anyo", "mes"], "importe": ["territorio", "tipo_corte", "anyo", "mes"]}
OPTIONAL_DATASETS = ("importe",)


class SeguridadSocialTransform:
    def __init__(self, config):
        source_config = config["sources"]["seguridad_social"]
        silver_config = config["silver"]["seguridad_social"]
        self.source_name = source_config["name"]
        self.files = source_config["files"]
        self.territorio = silver_config["territorio"]
        names = ("afiliados", "pensiones") + tuple(name for name in OPTIONAL_DATASETS if name in silver_config)
        self.datasets = {name: silver_config[name] for name in names}
        self.schemas = {"afiliados": AfiliadosSchema(), "pensiones": PensionesSchema(), "importe": ImporteSchema()}
        self.reader = SeguridadSocialBronzeReader(source_config["storage"])
        self.afiliados_parser = AfiliadosParser(silver_config["afiliados"])
        self.pensiones_parser = PensionesParser(silver_config["pensiones"])
        self.importe_parser = PensionesParser(silver_config["importe"]) if "importe" in self.datasets else None
        self.quality = SeguridadSocialQuality(silver_config, config["quality"])
        self.writer = DatasetWriter(config["output"], silver_config["output_path"])
        self.manifest = RunManifest(silver_config["manifests_path"])
        self.report = QualityReport(silver_config["manifests_path"], LAYER)
        self.logger = get_logger(__name__)

    def run(self, bronze_integrity):
        started_at = datetime.now(timezone.utc)
        run_id = f"silver_seguridad_social_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
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
            raise RuntimeError("La integridad de Bronce de Seguridad Social no está en verde; Plata no lee payloads sin verificar.")
        payloads = self.reader.latest_payloads(sorted({dataset["source_file"] for dataset in self.datasets.values()}))
        afiliados_payload = payloads[self.datasets["afiliados"]["source_file"]]
        pensiones_payload = payloads[self.datasets["pensiones"]["source_file"]]
        afiliados = self.afiliados_parser.parse(self._grid(afiliados_payload))
        parsed_pensiones = self.pensiones_parser.parse(self._grid(pensiones_payload))
        evaluation.metrics["pensiones_periodos_no_publicados"] = parsed_pensiones["unpublished"]
        frames = {
            "afiliados": self._finish("afiliados", afiliados, afiliados_payload),
            "pensiones": self._finish("pensiones", parsed_pensiones["frame"], pensiones_payload),
        }
        if self.importe_parser is not None:
            importe_payload = payloads[self.datasets["importe"]["source_file"]]
            parsed_importe = self.importe_parser.parse(self._grid(importe_payload, self.datasets["importe"].get("sheet")))
            evaluation.metrics["importe_periodos_no_publicados"] = parsed_importe["unpublished"]
            frames["importe"] = self._finish("importe", parsed_importe["frame"].assign(unidad=self.datasets["importe"]["unidad"]), importe_payload)
        if not self.quality.evaluate(frames["afiliados"], frames["pensiones"], evaluation, started_at.date(), frames.get("importe")).passed():
            raise ValueError(evaluation.rejection(LAYER))
        outputs = {name: Path(self.writer.write(frame, self.schemas[name], self.datasets[name]["dataset_name"])) for name, frame in frames.items()}
        summary = {name: self._summary(frame) for name, frame in frames.items()}
        inputs = list({payload["file_id"]: payload for payload in (afiliados_payload, pensiones_payload)}.values())
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, inputs, outputs, frames, summary))
        for name, frame in frames.items():
            self.logger.detail(f"{LAYER} | {self.datasets[name]['dataset_name']}: {len(frame)} filas ({summary[name]['desde']} a {summary[name]['hasta']})")
        return {
            "run_id": run_id,
            "bronze_run_ids": sorted({payload["run_id"] for payload in inputs}),
            "paths": {name: str(path) for name, path in outputs.items()},
            "manifest_path": manifest_path,
            "rows": {self.datasets[name]["dataset_name"]: len(frame) for name, frame in frames.items()},
            "summary": summary,
        }

    def _grid(self, payload, sheet=None):
        return self.reader.read_sheet(payload, sheet or self.files[payload["file_id"]]["sheet"])

    def _finish(self, name, frame, payload):
        schema = self.schemas[name]
        frame = frame.assign(
            fuente=self.source_name,
            archivo_id=payload["file_id"],
            run_id=payload["run_id"],
            territorio=self.territorio,
            estado_dato=self.files[payload["file_id"]]["data_state"],
        )
        return frame[schema.columns()].astype(schema.dtypes).sort_values(SORT_ORDER[name], ignore_index=True)

    def _summary(self, frame):
        summary = {"filas": len(frame), "desde": str(frame["fecha_referencia"].min()), "hasta": str(frame["fecha_referencia"].max())}
        if "tipo_corte" in frame:
            summary["filas_por_tipo_corte"] = {str(key): int(value) for key, value in frame.groupby("tipo_corte").size().items()}
        return summary

    def _manifest(self, run_id, started_at, inputs, outputs, frames, summary):
        payloads = []
        for name, path in outputs.items():
            with path.open("rb") as file:
                sha256 = hashlib.file_digest(file, "sha256").hexdigest()
            payloads.append(
                {
                    "dataset": self.datasets[name]["dataset_name"],
                    "path": self.manifest.relative_path(path),
                    "sha256": sha256,
                    "size_bytes": path.stat().st_size,
                    "rows": len(frames[name]),
                }
            )
        return {
            "run_id": run_id,
            "quality_report": f"{run_id}.quality.json",
            "datasets": [self.datasets[name]["dataset_name"] for name in outputs],
            "status": "completada",
            "started_at_utc": self._iso(started_at),
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "bronze_inputs": [
                {"file_id": payload["file_id"], "run_id": payload["run_id"], "sha256": payload["sha256"], "path": self.manifest.relative_path(payload["path"])}
                for payload in inputs
            ],
            "bronze_run_ids": sorted({payload["run_id"] for payload in inputs}),
            "rows_summary": {self.datasets[name]["dataset_name"]: value for name, value in summary.items()},
            "payloads": payloads,
        }

    def _iso(self, moment):
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
