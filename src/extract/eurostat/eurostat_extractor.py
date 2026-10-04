from datetime import datetime, timezone
import json

from src.extract.bronze_storage import BronzeStorage
from src.extract.http_client import HttpClient
from src.utils.run_manifest import RunManifest
from src.logger import get_logger

JSONSTAT_VERSION = "2.0"


class EurostatExtractor:
    """Descarga conjuntos de la API de difusión de Eurostat (JSON-stat 2.0) y los guarda sin modificar en Bronce."""

    def __init__(self, config):
        self.source_name = config["name"]
        self.base_url = config["base_url"]
        self.common_parameters = config.get("common_parameters", {})
        self.datasets = config["datasets"]
        self.http = HttpClient(config["request"])
        self.storage = BronzeStorage(config["storage"]["payloads_path"])
        self.manifest = RunManifest(config["storage"]["manifests_path"])
        self.logger = get_logger(__name__)

    def extract_datasets(self, dataset_ids):
        started_at = datetime.now(timezone.utc)
        run = {"run_id": f"eurostat_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}", "started_at_utc": self._iso(started_at)}
        records = []
        try:
            for dataset_id in dataset_ids:
                records.append(self.extract_dataset(dataset_id))
        except (OSError, ValueError, RuntimeError) as error:
            self._write_manifest(run, dataset_ids, records, error)
            raise
        return self._write_manifest(run, dataset_ids, records, None)

    def extract_dataset(self, dataset_id):
        dataset = self.datasets.get(dataset_id)
        if dataset is None:
            raise ValueError(f"El conjunto {dataset_id} no está configurado en sources.eurostat.datasets de config/config.yaml.")
        url = f"{self.base_url}/{dataset['code']}"
        parameters = {**self.common_parameters, **dataset["filters"]}
        response = self.http.get(url, params=parameters)
        validations = self._validate(dataset_id, dataset, response.content)
        stored = self.storage.save(response.content, dataset_id, "json")
        record = {
            "source": self.source_name,
            "dataset_id": dataset_id,
            "code": dataset["code"],
            "name": dataset["name"],
            "url": response.url,
            "parameters": parameters,
            "status_code": response.status_code,
            "size_bytes": stored["size_bytes"],
            "sha256": stored["sha256"],
            "downloaded_at_utc": stored["downloaded_at_utc"],
            "source_updated": validations["source_updated"],
            "path": stored["path"],
            "validations": validations,
        }
        size = f"{stored['size_bytes'] / 1_000:.1f} KB".replace(".", ",")
        self.logger.ok(
            f"{dataset_id} · {dataset['code']}: HTTP {response.status_code}, {size}, "
            f"{validations['observations']} observaciones (actualizado en origen {validations['source_updated']})"
        )
        return record

    def close(self):
        self.http.close()

    @property
    def closed(self):
        """True cuando la conexión HTTP del extractor está cerrada."""
        return self.http.closed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    def _validate(self, dataset_id, dataset, content):
        description = f"La respuesta de Eurostat para {dataset_id} ({dataset['code']})"
        if not content:
            raise ValueError(f"{description} llegó vacía; no se guarda ningún archivo.")
        try:
            payload = json.loads(content)
        except ValueError as error:
            raise ValueError(f"{description} no es JSON válido: {error}; no se guarda ningún archivo.") from error
        if not isinstance(payload, dict) or "error" in payload:
            raise ValueError(f"{description} es un error de la API: {payload.get('error') if isinstance(payload, dict) else payload}; no se guarda ningún archivo.")
        missing = [key for key in ("id", "size", "dimension", "value") if key not in payload]
        if missing:
            raise ValueError(f"{description} no tiene la estructura JSON-stat esperada (faltan {missing}); no se guarda ningún archivo.")
        if str(payload.get("version")) != JSONSTAT_VERSION:
            raise ValueError(f"{description} usa JSON-stat {payload.get('version')!r}; se esperaba {JSONSTAT_VERSION}.")
        if not payload["value"]:
            raise ValueError(f"{description} no contiene observaciones con los filtros configurados; no se guarda ningún archivo.")
        return {
            "json_valid": True,
            "jsonstat_version": payload["version"],
            "dimensions": payload["id"],
            "observations": len(payload["value"]),
            "source_updated": payload.get("updated"),
            "label": payload.get("label"),
        }

    def _write_manifest(self, run, dataset_ids, records, error):
        manifest = {
            "run_id": run["run_id"],
            "source": self.source_name,
            "status": "fallida" if error else "completada",
            "error": str(error) if error else None,
            "started_at_utc": run["started_at_utc"],
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "datasets_requested": list(dataset_ids),
            "payloads": [self._manifest_entry(record) for record in records],
        }
        return {"run_id": run["run_id"], "manifest_path": self.manifest.write(manifest), "records": records}

    def _manifest_entry(self, record):
        entry = {key: value for key, value in record.items() if key != "path"}
        entry["path"] = self.manifest.relative_path(record["path"])
        return entry

    def _iso(self, moment):
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
