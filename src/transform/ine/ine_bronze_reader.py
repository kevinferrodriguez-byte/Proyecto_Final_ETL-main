from pathlib import Path
import json


class IneBronzeReader:
    def __init__(self, storage_config):
        self.manifests_path = Path(storage_config["manifests_path"])
        self.unmanifested_path = Path(storage_config["unmanifested_path"]).resolve()

    def latest_payloads(self, table_ids):
        wanted = set(table_ids)
        latest = {}
        for manifest_path, manifest in self._completed_manifests():
            for entry in manifest["payloads"]:
                if entry["table_id"] not in wanted:
                    continue
                latest[(entry["table_id"], entry["query"])] = {
                    "table_id": entry["table_id"],
                    "query": entry["query"],
                    "run_id": manifest["run_id"],
                    "sha256": entry["sha256"],
                    "path": (manifest_path.parent / entry["path"]).resolve(),
                }
        missing = sorted(wanted - {table_id for table_id, query in latest})
        if missing:
            raise ValueError(f"No hay ejecuciones completadas de Bronce para las tablas INE {missing}.")
        unmanifested = [ref["path"].name for ref in latest.values() if ref["path"].is_relative_to(self.unmanifested_path)]
        if unmanifested:
            raise ValueError(f"Plata no puede leer payloads de {self.unmanifested_path}: {unmanifested}.")
        return [latest[key] for key in sorted(latest)]

    def read(self, payload):
        return json.loads(payload["path"].read_bytes())

    def _completed_manifests(self):
        manifests = []
        for manifest_path in self.manifests_path.glob("*.manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") == "completada":
                manifests.append((manifest_path, manifest))
        return sorted(manifests, key=lambda item: item[1]["started_at_utc"])
