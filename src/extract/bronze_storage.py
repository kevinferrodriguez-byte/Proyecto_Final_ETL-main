from datetime import datetime, timezone
from pathlib import Path
import hashlib

from src.logger import get_logger


class BronzeStorage:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.logger = get_logger(__name__)

    def save(self, content, prefix, extension):
        downloaded_at = datetime.now(timezone.utc)
        path = self.directory / f"{prefix}_{downloaded_at.strftime('%Y%m%dT%H%M%S.%fZ')}.{extension}"
        self.directory.mkdir(parents=True, exist_ok=True)

        try:
            with path.open("xb") as file:
                file.write(content)
        except FileExistsError as error:
            raise FileExistsError(
                f"El archivo {path} ya existe en Bronce y no se sobrescribe. Repita la descarga para generar una nueva marca de tiempo."
            ) from error
        except OSError:
            path.unlink(missing_ok=True)
            raise

        stored = {
            "path": str(path),
            "downloaded_at_utc": downloaded_at.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        self.logger.detail(f"Archivo guardado en Bronce: {path} ({stored['size_bytes']} bytes, sha256 {stored['sha256']})")
        return stored
