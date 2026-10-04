from pathlib import Path
import hashlib
import json

import pandas as pd


class SilverReader:
    def __init__(self, manifests_path, dataset_name):
        self.manifests_path = Path(manifests_path)
        self.dataset_name = dataset_name

    def latest(self):
        manifest_path, manifest = self._latest_completed()
        entries = [entry for entry in manifest["payloads"] if entry.get("dataset") == self.dataset_name]
        if len(entries) != 1:
            raise ValueError(f"El manifiesto de Plata {manifest_path.name} no registra exactamente un conjunto {self.dataset_name}.")
        entry = entries[0]
        path = (manifest_path.parent / entry["path"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"No existe {path}, registrado en el manifiesto de Plata {manifest_path.name}.")
        with path.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
        if sha256 != entry["sha256"] or path.stat().st_size != entry["size_bytes"]:
            raise ValueError(
                f"{path.name} no coincide con el manifiesto de Plata {manifest_path.name} (sha256 o tamaño distintos); "
                "vuelva a ejecutar Plata antes de construir Oro."
            )
        return {
            "run_id": manifest["run_id"],
            "bronze_run_ids": manifest.get("bronze_run_ids", []),
            "manifest": manifest_path.name,
            "path": path,
            "sha256": sha256,
            "frame": pd.read_parquet(path),
        }

    def _latest_completed(self):
        completed = []
        for manifest_path in self.manifests_path.glob("*.manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") == "completada":
                completed.append((manifest["started_at_utc"], manifest_path, manifest))
        if not completed:
            raise ValueError(f"No hay manifiestos de Plata completados en {self.manifests_path}.")
        latest = max(completed, key=lambda item: item[0])
        return latest[1], latest[2]
