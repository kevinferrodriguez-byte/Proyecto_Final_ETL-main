from src.extract.ine.ine_filter_resolver import IneFilterResolver
from src.utils.run_manifest import RunManifest
from src.extract.bronze_storage import BronzeStorage
from src.extract.ine.ine_api import IneApi
from datetime import timezone, datetime
from src.logger import get_logger


class IneExtractor:
    def __init__(self, config):
        self.source_name = config["name"]
        self.tables = config["tables"]
        self.api = IneApi(config)
        self.resolver = IneFilterResolver(self.api)
        self.storage = BronzeStorage(config["storage"]["payloads_path"])
        self.manifest = RunManifest(config["storage"]["manifests_path"])
        self.logger = get_logger(__name__)

    def extract_tables(self, table_ids):
        started_at = datetime.now(timezone.utc)
        run = {"run_id": f"ine_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}", "started_at_utc": self._iso(started_at)}
        records = []
        try:
            for table_id in table_ids:
                records.extend(self.extract_table(table_id))
        except (OSError, ValueError, RuntimeError) as error:
            self._write_manifest(run, table_ids, records, error)
            raise
        return self._write_manifest(run, table_ids, records, None)

    def extract_table(self, table_id):
        table = self.tables.get(table_id)
        if table is None:
            raise ValueError(f"La tabla INE {table_id} no está configurada en sources.ine.tables de config/config.yaml.")

        queries = [{"name": "detalle", "filters": table["filters"]}] + table.get("control_queries", [])
        tv_filters_by_query = {query["name"]: self.resolver.resolve(table_id, query["filters"]) for query in queries}
        downloads = {query_name: self.api.table_data(table_id, tv_filters) for query_name, tv_filters in tv_filters_by_query.items()}
        records = [self._store(table_id, query_name, tv_filters_by_query[query_name], download) for query_name, download in downloads.items()]
        statuses = ", ".join(sorted({str(record["status_code"]) for record in records}))
        queries = "1 consulta descargada" if len(records) == 1 else f"{len(records)} consultas descargadas"
        size = self._size(sum(record["size_bytes"] for record in records))
        self.logger.ok(f"{table_id} · {table['name']}: {queries} (HTTP {statuses}, {size})")
        self.logger.detail(
            f"Tabla INE {table_id} descargada: "
            + ", ".join(f"{record['query']} (HTTP {record['status_code']}, {record['size_bytes']} bytes)" for record in records)
        )
        return records

    def close(self):
        self.api.close()

    @property
    def closed(self):
        """True cuando la conexión HTTP del extractor está cerrada."""
        return self.api.http.closed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    def _size(self, size_bytes):
        if size_bytes >= 1_000_000:
            return f"{size_bytes / 1_000_000:.2f} MB".replace(".", ",")
        return f"{size_bytes / 1_000:.1f} KB".replace(".", ",")

    def _store(self, table_id, query_name, tv_filters, download):
        response = download["response"]
        stored = self.storage.save(response.content, f"{table_id}_{query_name}", "json")
        return {
            "source": self.source_name,
            "table_id": table_id,
            "query": query_name,
            "url": response.url,
            "parameters": self._parameters(tv_filters),
            "status_code": response.status_code,
            "size_bytes": stored["size_bytes"],
            "sha256": stored["sha256"],
            "downloaded_at_utc": stored["downloaded_at_utc"],
            "path": stored["path"],
            "validations": download["validations"],
        }

    def _parameters(self, tv_filters):
        parameters = {"tv": tv_filters}
        parameters.update(self.api.data_parameters)
        return parameters

    def _write_manifest(self, run, table_ids, records, error):
        manifest = {
            "run_id": run["run_id"],
            "source": self.source_name,
            "status": "fallida" if error else "completada",
            "error": str(error) if error else None,
            "started_at_utc": run["started_at_utc"],
            "finished_at_utc": self._iso(datetime.now(timezone.utc)),
            "tables_requested": list(table_ids),
            "payloads": [self._manifest_entry(record) for record in records],
        }
        return {"run_id": run["run_id"], "manifest_path": self.manifest.write(manifest), "records": records}

    def _manifest_entry(self, record):
        entry = {key: value for key, value in record.items() if key != "path"}
        entry["path"] = self.manifest.relative_path(record["path"])
        entry["known_behaviors"] = self.tables[record["table_id"]].get("known_behaviors", [])
        return entry

    def _iso(self, moment):
        return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
