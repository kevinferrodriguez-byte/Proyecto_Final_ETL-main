from pathlib import Path
import json


class EurostatBronzeReader:
    """Localiza el payload más reciente de cada conjunto en manifiestos completados de Bronce."""

    def __init__(self, storage_config):
        self.manifests_path = Path(storage_config["manifests_path"])
        self.unmanifested_path = Path(storage_config["unmanifested_path"]).resolve()

    def latest_payloads(self, dataset_ids):
        wanted = set(dataset_ids)
        latest = {}
        for manifest_path, manifest in self._completed_manifests():
            for entry in manifest["payloads"]:
                if entry["dataset_id"] not in wanted:
                    continue
                latest[entry["dataset_id"]] = {
                    "dataset_id": entry["dataset_id"],
                    "run_id": manifest["run_id"],
                    "sha256": entry["sha256"],
                    "source_updated": entry.get("source_updated"),
                    "path": (manifest_path.parent / entry["path"]).resolve(),
                }
        missing = sorted(wanted - set(latest))
        if missing:
            raise ValueError(f"No hay ejecuciones completadas de Bronce para los conjuntos de Eurostat {missing}.")
        unmanifested = [ref["path"].name for ref in latest.values() if ref["path"].is_relative_to(self.unmanifested_path)]
        if unmanifested:
            raise ValueError(f"Plata no puede leer payloads de {self.unmanifested_path}: {unmanifested}.")
        return latest

    def read(self, payload):
        return json.loads(payload["path"].read_bytes())

    def _completed_manifests(self):
        manifests = []
        for manifest_path in self.manifests_path.glob("*.manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") == "completada":
                manifests.append((manifest_path, manifest))
        return sorted(manifests, key=lambda item: item[1]["started_at_utc"])
