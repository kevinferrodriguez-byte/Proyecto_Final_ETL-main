from datetime import datetime, timezone
from pathlib import Path
import json

from src.logger import get_logger


class QualityReport:
    def __init__(self, directory, layer):
        self.directory = Path(directory)
        self.layer = layer
        self.logger = get_logger(__name__)

    def write(self, run_id, evaluation, cause):
        report = {
            "run_id": run_id,
            "capa": self.layer,
            "estado": "rechazado" if cause else "aprobado",
            "generado_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "causa_rechazo": cause,
            "resumen": evaluation.summary(),
            "metricas": evaluation.metrics,
            "reglas": evaluation.rules,
        }
        path = self.directory / f"{run_id}.quality.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2, default=str)
            file.write("\n")
        summary = report["resumen"]
        if cause:
            self.logger.error(f"Calidad de {self.layer} rechazada ({self._breakdown(summary)}); detalle en {path}")
        elif summary["aprobadas"] == len(evaluation.rules):
            self.logger.ok(f"Calidad de {self.layer} aprobada: {summary['aprobadas']} de {len(evaluation.rules)} reglas cumplen")
        else:
            self.logger.ok(f"Calidad de {self.layer} aprobada: {self._breakdown(summary)}")
        self.logger.detail(f"Reporte de calidad de {self.layer} ({report['estado']}): {path}")
        return str(path)

    def _breakdown(self, summary):
        parts = [
            self._count(summary["aprobadas"], "regla aprobada", "reglas aprobadas"),
            self._count(summary["advertencias"], "advertencia", "advertencias"),
            self._count(summary["fallas"], "falla", "fallas"),
        ]
        if summary["no_evaluadas"]:
            parts.append(self._count(summary["no_evaluadas"], "no evaluada", "no evaluadas"))
        return " · ".join(parts)

    def _count(self, value, singular, plural):
        return f"{value} {singular if value == 1 else plural}"
