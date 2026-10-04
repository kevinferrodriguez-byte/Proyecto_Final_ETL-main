from pathlib import Path
import json
import zipfile

import pandas as pd


class SeguridadSocialBronzeReader:
    def __init__(self, storage_config):
        self.manifests_path = Path(storage_config["manifests_path"])
        self.unmanifested_path = Path(storage_config["unmanifested_path"]).resolve()

    def latest_payloads(self, file_ids):
        wanted = set(file_ids)
        latest = {}
        for manifest_path, manifest in self._completed_manifests():
            for entry in manifest["payloads"]:
                if entry["file_id"] not in wanted:
                    continue
                latest[entry["file_id"]] = {
                    "file_id": entry["file_id"],
                    "run_id": manifest["run_id"],
                    "sha256": entry["sha256"],
                    "path": (manifest_path.parent / entry["path"]).resolve(),
                }
        missing = sorted(wanted - set(latest))
        if missing:
            raise ValueError(f"No hay ejecuciones completadas de Bronce para los archivos de Seguridad Social {missing}.")
        unmanifested = [ref["path"].name for ref in latest.values() if ref["path"].is_relative_to(self.unmanifested_path)]
        if unmanifested:
            raise ValueError(f"Plata no puede leer payloads de {self.unmanifested_path}: {unmanifested}.")
        return latest

    def read_sheet(self, payload, sheet):
        try:
            with pd.ExcelFile(payload["path"], engine="openpyxl") as workbook:
                if sheet not in workbook.sheet_names:
                    raise ValueError(
                        f"El payload {payload['path'].name} no contiene la hoja '{sheet}' (hojas: {', '.join(workbook.sheet_names)})."
                    )
                return workbook.parse(sheet, header=None, dtype=object)
        except (zipfile.BadZipFile, KeyError) as error:
            raise ValueError(f"El payload {payload['path'].name} no se puede leer como libro Excel: {error}.") from error

    def _completed_manifests(self):
        manifests = []
        for manifest_path in self.manifests_path.glob("*.manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") == "completada":
                manifests.append((manifest_path, manifest))
        return sorted(manifests, key=lambda item: item[1]["started_at_utc"])
