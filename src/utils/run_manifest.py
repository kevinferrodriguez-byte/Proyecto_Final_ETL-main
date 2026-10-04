from pathlib import Path
import json
import os

from src.logger import get_logger


class RunManifest:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.logger = get_logger(__name__)

    def relative_path(self, payload_path):
        return Path(os.path.relpath(payload_path, self.directory)).as_posix()

    def write(self, manifest):
        path = self.directory / f"{manifest['run_id']}.manifest.json"
        orphans = ", ".join(Path(payload["path"]).name for payload in manifest["payloads"]) or "ninguno"
        content = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise OSError(
                f"No se pudo crear la carpeta de manifiestos {self.directory}: {error}. Payloads sin manifiesto: {orphans}."
            ) from error

        try:
            with path.open("xb") as file:
                file.write(content)
        except FileExistsError as error:
            raise FileExistsError(
                f"El manifiesto {path} ya existe y no se sobrescribe. Payloads sin manifiesto: {orphans}."
            ) from error
        except OSError as error:
            path.unlink(missing_ok=True)
            raise OSError(f"No se pudo escribir el manifiesto {path}: {error}. Payloads sin manifiesto: {orphans}.") from error

        self.logger.detail(f"Manifiesto guardado: {path} ({len(manifest['payloads'])} payloads)")
        return str(path)
