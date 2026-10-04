from datetime import datetime, timezone
from pathlib import Path
import json
import time



class PipelineRunLog:
    def __init__(self, directory, start_stage, stages):
        self.directory = Path(directory)
        self.started_at = datetime.now(timezone.utc)
        self.started_clock = time.perf_counter()
        self.run_id = f"pipeline_{self.started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
        self.record = {
            "run_id": self.run_id,
            "desde": start_stage,
            "etapas_previstas": list(stages),
            "inicio_utc": self._iso(self.started_at),
            "estado": "en_curso",
            "error": None,
            "etapas": [],
            "run_ids": {},
        }
        self.current = None

    def start(self, stage):
        self.current = {"etapa": stage, "inicio_utc": self._iso(datetime.now(timezone.utc)), "clock": time.perf_counter()}

    def finish(self, details):
        self._close("correcta", details)

    def fail(self, error):
        if self.current is not None:
            self._close("fallida", {"error": str(error)})
        self.record["estado"] = "fallida"
        self.record["error"] = str(error)

    def link(self, step, run_id):
        """Enlaza el run_id que produjo un paso (manifiesto de Bronce, Plata u Oro) con esta ejecución."""
        if run_id is not None:
            self.record["run_ids"][step] = run_id

    def write(self):
        if self.record["estado"] == "en_curso":
            self.record["estado"] = "completada"
        self.record["fin_utc"] = self._iso(datetime.now(timezone.utc))
        self.record["duracion_s"] = round(time.perf_counter() - self.started_clock, 3)
        path = self.directory / f"{self.run_id}.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            json.dump(self.record, file, ensure_ascii=False, indent=2)
            file.write("\n")
        return str(path)

    def _close(self, result, details):
        stage = {
            "etapa": self.current["etapa"],
            "resultado": result,
            "inicio_utc": self.current["inicio_utc"],
            "duracion_s": round(time.perf_counter() - self.current["clock"], 3),
        }
        stage.update(details)
        self.record["etapas"].append(stage)
        self.current = None

    def _iso(self, moment):
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
