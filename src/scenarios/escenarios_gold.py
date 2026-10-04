from datetime import datetime, timezone
from pathlib import Path
import hashlib

from src.indicators.kpi_schema import KpiSchema
from src.logger import get_logger
from src.model.modelo_schema import TOTAL_AGE_GROUP
from src.quality.escenarios_quality import EscenariosQuality
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.scenarios.proyecciones import Proyecciones
from src.transform.demografia_schema import DemografiaSchema
from src.utils.dataset_writer import DatasetWriter
from src.utils.run_manifest import RunManifest
from src.utils.silver_reader import SilverReader

LAYER = "Oro escenarios"
MODEL_DIMENSIONS = ("dim_tiempo", "dim_territorio", "dim_sexo", "dim_grupo_edad", "dim_fuente", "dim_indicador")
OUTPUTS = ("dim_escenario", "fact_proyecciones_demograficas", "dm_escenarios_2050")


class EscenariosGold:
    """Oro · capa de escenarios, separada del ETL y de los indicadores observados.

    Consume las proyecciones oficiales ya integradas (kpis_demograficos proyectados y población proyectada de
    Plata) y las dimensiones conformadas del modelo. No produce ninguna proyección propia.
    """

    def __init__(self, config):
        silver = config["silver"]
        demography = config["indicadores"]["demografia"]
        model = config["modelo"]
        scenarios = config["escenarios"]
        self.readers = {
            "kpis_demograficos": SilverReader(demography["manifests_path"], demography["dataset_name"]),
            "stg_poblacion_anual": SilverReader(silver["manifests_path"], silver["dataset_name"]),
            "fact_indicadores_anual": SilverReader(model["manifests_path"], "fact_indicadores_anual"),
        }
        self.dimension_readers = {name: SilverReader(model["manifests_path"], name) for name in MODEL_DIMENSIONS}
        self.input_schemas = {"kpis_demograficos": KpiSchema(), "stg_poblacion_anual": DemografiaSchema()}
        self.projections = Proyecciones(config)
        self.quality = EscenariosQuality(config)
        self.writer = DatasetWriter(config["output"], scenarios["output_path"])
        self.manifest = RunManifest(scenarios["manifests_path"])
        self.report = QualityReport(scenarios["manifests_path"], LAYER)
        self.logger = get_logger(__name__)

    def run(self):
        started_at = datetime.now(timezone.utc)
        run_id = f"gold_escenarios_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
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
        model_dimensions = {name: reader.latest() for name, reader in self.dimension_readers.items()}
        evaluation.metrics["entradas"] = {name: source["run_id"] for name, source in {**inputs, **model_dimensions}.items()}
        problems = [f"{name}: {problem}" for name, schema in self.input_schemas.items() for problem in schema.problems(inputs[name]["frame"])]
        if not evaluation.check("entradas_esquema", "QLT-001: cada entrada cumple su esquema", problems):
            raise ValueError(evaluation.rejection(LAYER))
        if not evaluation.check("linaje_coherente", "ESC-00: proyecciones y dimensiones proceden de las ejecuciones leídas", self._lineage(inputs, model_dimensions)):
            raise ValueError(evaluation.rejection(LAYER))
        integrated = self.projections.integrate(inputs["kpis_demograficos"], inputs["stg_poblacion_anual"])
        natural = integrated["frame"]
        dimensions = {name: source["frame"] for name, source in model_dimensions.items()}
        dimensions["dim_escenario"] = self.projections.dim_escenario(natural["escenario"].unique())
        fact = self.projections.assign_keys(natural, dimensions, run_id, started_at)
        mart = self.projections.mart_2050(natural, self._last_observed(inputs["fact_indicadores_anual"]["frame"], dimensions), run_id)
        layer = {
            "dimensions": dimensions,
            "fact": fact,
            "mart": mart,
            "schemas": self.projections.schemas,
            "expected_rows": integrated["rows_by_part"],
            "scenarios_present": sorted(natural["escenario"].unique()),
        }
        if not self.quality.evaluate(layer, evaluation).passed():
            raise ValueError(evaluation.rejection(LAYER))
        frames = {"dim_escenario": dimensions["dim_escenario"], "fact_proyecciones_demograficas": fact, "dm_escenarios_2050": mart}
        outputs = {name: (Path(self.writer.write(frames[name], self.projections.schemas[name], name)), len(frames[name])) for name in OUTPUTS}
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, {**inputs, **model_dimensions}, outputs))
        self.logger.detail(f"{LAYER}: {len(fact)} filas proyectadas; manifiesto {manifest_path}")
        return {
            "run_id": run_id,
            "input_run_ids": evaluation.metrics["entradas"],
            "paths": {name: str(path) for name, (path, _) in outputs.items()},
            "manifest_path": manifest_path,
            "rows": {name: rows for name, (_, rows) in outputs.items()},
        }

    def _lineage(self, inputs, model_dimensions):
        problems = []
        kpi_silver = sorted(inputs["kpis_demograficos"]["frame"]["silver_run_id"].unique())
        if kpi_silver != [inputs["stg_poblacion_anual"]["run_id"]]:
            problems.append(f"kpis_demograficos procede de Plata {kpi_silver} y la Plata INE leída es {inputs['stg_poblacion_anual']['run_id']}")
        model_runs = {source["run_id"] for source in model_dimensions.values()} | {inputs["fact_indicadores_anual"]["run_id"]}
        if len(model_runs) != 1:
            problems.append(f"las dimensiones y los hechos del modelo proceden de ejecuciones distintas: {sorted(model_runs)}")
        return problems

    def _last_observed(self, fact, dimensions):
        frame = fact.merge(dimensions["dim_indicador"][["indicador_key", "codigo_indicador"]], on="indicador_key")
        frame = frame.merge(dimensions["dim_sexo"][["sexo_key", "codigo_sexo"]], on="sexo_key")
        frame = frame.merge(dimensions["dim_grupo_edad"][["grupo_edad_key", "codigo_grupo"]], on="grupo_edad_key")
        frame = frame.merge(dimensions["dim_territorio"][["territorio_key", "codigo_territorio"]], on="territorio_key")
        frame = frame[frame["codigo_sexo"].eq("total")].sort_values("tiempo_key")
        last = frame.groupby(["codigo_territorio", "codigo_indicador", "codigo_grupo"]).tail(1)
        return last.rename(
            columns={"codigo_territorio": "territorio", "codigo_indicador": "indicador", "codigo_grupo": "grupo_edad", "tiempo_key": "anyo_ultimo_observado", "valor": "valor_ultimo_observado"}
        )[["territorio", "indicador", "grupo_edad", "anyo_ultimo_observado", "valor_ultimo_observado"]].assign(grupo_edad=lambda data: data["grupo_edad"].fillna(TOTAL_AGE_GROUP))

    def _manifest(self, run_id, started_at, inputs, outputs):
        payloads = []
        for name, (path, rows) in outputs.items():
            with path.open("rb") as file:
                sha256 = hashlib.file_digest(file, "sha256").hexdigest()
            payloads.append({"dataset": name, "path": self.manifest.relative_path(path), "sha256": sha256, "size_bytes": path.stat().st_size, "rows": rows})
        return {
            "run_id": run_id,
            "dataset": "fact_proyecciones_demograficas",
            "status": "completada",
            "nota": "Capa de escenarios: integra las Proyecciones de Población oficiales del INE; no contiene modelación propia.",
            "started_at_utc": self._iso(started_at),
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "quality_report": f"{run_id}.quality.json",
            "inputs": [
                {"dataset": name, "run_id": source["run_id"], "manifest": source["manifest"], "path": self.manifest.relative_path(source["path"]), "sha256": source["sha256"]}
                for name, source in inputs.items()
            ],
            "payloads": payloads,
        }

    def _iso(self, moment):
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
