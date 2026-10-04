from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import time

import pandas as pd

from src.logger import get_logger
from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport
from src.serving.esquema_relacional import POSTGRES_TYPES, SQLITE_TYPES, TABLES, VIEWS, create_table, load_order, logical_type
from src.utils.run_manifest import RunManifest
from src.utils.silver_reader import SilverReader

LAYER = "Carga"
DETAIL_LIMIT = 500
REPLACE_ATTEMPTS = 5
REPLACE_BACKOFF_SECONDS = 1.0
SQLITE_LOCK_TIMEOUT_SECONDS = 30
LOCK_HINT = (
    "está abierto en otro programa (Power BI, Excel, DB Browser, un visor de SQLite de VS Code o un notebook con la conexión "
    "abierta) o bloqueado por la sincronización de OneDrive. Ciérrelo o pause la sincronización y repita con: python main.py --desde carga"
)
RULES = (
    ("conteo_filas", "CAR-01: filas en SQLite y en CSV = filas de los Parquet de Oro (conteo antes y después de la carga)"),
    ("integridad_referencial", "CAR-02: PRAGMA foreign_key_check sin violaciones"),
    ("vistas_consultables", "CAR-03: las vistas de consumo se ejecutan y devuelven filas"),
)


class Carga:
    """Publica la capa Oro para su consumo: SQLite (verificado), CSV (Power BI) y scripts de PostgreSQL.

    Solo lee Parquet registrados en manifiestos completados (sha256 verificado). La base se reconstruye
    completa en cada ejecución en un archivo temporal y se sustituye de forma atómica.
    """

    def __init__(self, config):
        self.config = config
        load = config["carga"]
        self.output_path = Path(load["output_path"])
        self.sqlite_path = self.output_path / load["sqlite_file"]
        self.csv_dir = self.output_path / load["csv_dir"]
        self.postgres_dir = self.output_path / load["postgresql_dir"]
        self.postgres_schema = load["postgresql_schema"]
        self.manifest = RunManifest(load["manifests_path"])
        self.report = QualityReport(load["manifests_path"], LAYER)
        self.logger = get_logger(__name__)
        manifests = {"modelo": config["modelo"]["manifests_path"], "escenarios": config["escenarios"]["manifests_path"]}
        self.readers = {name: SilverReader(manifests[spec["layer"]], name) for name, spec in TABLES.items() if spec["layer"] in manifests}
        integrated = config["indicadores"]["integrados"]
        self.readers["aux_kpis_integrados"] = SilverReader(integrated["manifests_path"], integrated["dataset_name"])

    def run(self):
        started_at = datetime.now(timezone.utc)
        run_id = f"carga_{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
        evaluation = QualityEvaluation()
        try:
            result = self._build(run_id, started_at, evaluation)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            self.report.write(run_id, evaluation, str(error))
            if isinstance(error, sqlite3.Error):
                raise RuntimeError(f"Error de SQLite durante la carga: {error}") from error
            raise
        result["quality_report_path"] = self.report.write(run_id, evaluation, None)
        return result

    def _build(self, run_id, started_at, evaluation):
        sources = {name: reader.latest() for name, reader in self.readers.items()}
        frames = {name: source["frame"] for name, source in sources.items()}
        frames["aux_linaje"] = self._lineage(sources)
        frames["aux_calidad_reglas"] = self._quality_rules()
        frames = {name: frames[name] for name in load_order()}
        evaluation.metrics["filas_origen"] = {name: len(frame) for name, frame in frames.items()}
        self.output_path.mkdir(parents=True, exist_ok=True)
        counts = self._write_sqlite(frames)
        csv_counts = self._write_csv(frames)
        postgres = self._write_postgres(frames)
        count_problems = [
            f"{name}: Parquet {len(frame)} · SQLite {counts['tables'][name]} · CSV {csv_counts[name]}"
            for name, frame in frames.items()
            if not len(frame) == counts["tables"][name] == csv_counts[name]
        ]
        evaluation.metrics["filas_sqlite"] = counts["tables"]
        evaluation.metrics["filas_vistas"] = counts["views"]
        fk_problems = [f"{len(counts['fk_violations'])} violaciones de clave foránea; por ejemplo {counts['fk_violations'][:5]}"] if counts["fk_violations"] else []
        view_problems = [f"la vista {name} no devuelve filas" for name, rows in counts["views"].items() if rows == 0]
        for (name, description), problems in zip(RULES, (count_problems, fk_problems, view_problems)):
            evaluation.check(name, description, problems)
        if not evaluation.passed():
            raise ValueError(evaluation.rejection(LAYER))
        outputs = [self.sqlite_path, *sorted(self.csv_dir.glob("*.csv")), *postgres]
        manifest_path = self.manifest.write(self._manifest(run_id, started_at, sources, outputs, counts))
        return {
            "run_id": run_id,
            "manifest_path": manifest_path,
            "sqlite_path": str(self.sqlite_path),
            "csv_dir": str(self.csv_dir),
            "postgresql_dir": str(self.postgres_dir),
            "tables": len(frames),
            "views": len(VIEWS),
            "rows": counts["tables"],
        }

    def _lineage(self, sources):
        rows = [
            {"capa": TABLES[name]["layer"], "dataset": name, "run_id": source["run_id"], "manifiesto": source["manifest"], "sha256": source["sha256"], "filas": len(source["frame"]), "bronze_run_ids": ", ".join(source["bronze_run_ids"])}
            for name, source in sources.items()
        ]
        return pd.DataFrame(rows).astype({"filas": "int64"})

    def _quality_rules(self):
        """Consolida el último reporte de calidad de cada conjunto de Plata y Oro (KR 1.2 y 1.3)."""
        silver = self.config["silver"]
        indicators = self.config["indicadores"]
        directories = {
            "plata_ine": silver["manifests_path"],
            "plata_seguridad_social": silver["seguridad_social"]["manifests_path"],
            "plata_eurostat": silver["eurostat"]["manifests_path"],
            "indicadores_demografia": indicators["demografia"]["manifests_path"],
            "indicadores_pensiones": indicators["pensiones"]["manifests_path"],
            "indicadores_integrados": indicators["integrados"]["manifests_path"],
            "modelo": self.config["modelo"]["manifests_path"],
            "escenarios": self.config["escenarios"]["manifests_path"],
        }
        rows = []
        for layer, directory in directories.items():
            report = self._latest_report(Path(directory))
            if report is None:
                continue
            for rule in report["reglas"]:
                detail = " | ".join(map(str, rule["detalle"]))
                rows.append(
                    {
                        "capa": layer,
                        "run_id": report["run_id"],
                        "regla": rule["regla"],
                        "descripcion": rule["descripcion"],
                        "resultado": rule["resultado"],
                        "n_detalles": len(rule["detalle"]),
                        "detalle": detail[:DETAIL_LIMIT] + ("…" if len(detail) > DETAIL_LIMIT else ""),
                    }
                )
        return pd.DataFrame(rows, columns=["capa", "run_id", "regla", "descripcion", "resultado", "n_detalles", "detalle"]).astype({"n_detalles": "int64"})

    def _latest_report(self, directory):
        completed = []
        for path in directory.glob("*.manifest.json"):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("status") == "completada" and manifest.get("quality_report"):
                completed.append((manifest["started_at_utc"], directory / manifest["quality_report"]))
        if not completed:
            return None
        return json.loads(max(completed)[1].read_text(encoding="utf-8"))

    def _write_sqlite(self, frames):
        temporary = self.sqlite_path.with_suffix(".sqlite.tmp")
        temporary.unlink(missing_ok=True)
        connection = sqlite3.connect(temporary)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            for name, frame in frames.items():
                connection.execute(create_table(name, frame, SQLITE_TYPES))
                prepared = self._sqlite_values(frame)
                placeholders = ", ".join("?" for _ in frame.columns)
                connection.executemany(f"INSERT INTO {name} ({', '.join(frame.columns)}) VALUES ({placeholders})", prepared)
            for name, query in VIEWS.items():
                connection.execute(f"CREATE VIEW {name} AS {query}")
            connection.commit()
            tables = {name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in frames}
            views = {name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in VIEWS}
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            connection.close()
        self._publish_sqlite(temporary)
        return {"tables": tables, "views": views, "fk_violations": violations}

    def _publish_sqlite(self, temporary):
        """Publica la base ya construida y verificada sin sustituir el archivo.

        En Windows no se puede reemplazar (os.replace) un archivo que otro programa tiene abierto. La API de backup
        de SQLite copia la base temporal DENTRO del archivo existente: funciona aunque haya lectores conectados
        (espera a que terminen su lectura) y el cambio es atómico para ellos.
        """
        if not self.sqlite_path.exists():
            self._replace(temporary, self.sqlite_path)
            return
        source = sqlite3.connect(temporary)
        target = None
        try:
            target = sqlite3.connect(self.sqlite_path, timeout=SQLITE_LOCK_TIMEOUT_SECONDS)
            source.backup(target)
        except sqlite3.Error as error:
            raise RuntimeError(f"No se pudo actualizar {self.sqlite_path}: {error}. El archivo {LOCK_HINT}") from error
        finally:
            source.close()
            if target is not None:
                target.close()
        temporary.unlink(missing_ok=True)

    def _replace(self, temporary, path):
        """os.replace con reintentos: Windows y OneDrive bloquean el archivo de destino durante unos instantes."""
        for attempt in range(1, REPLACE_ATTEMPTS + 1):
            try:
                os.replace(temporary, path)
                return
            except PermissionError as error:
                if attempt == REPLACE_ATTEMPTS:
                    temporary.unlink(missing_ok=True)
                    raise PermissionError(f"No se pudo reemplazar {path} tras {REPLACE_ATTEMPTS} intentos: el archivo {LOCK_HINT}") from error
                self.logger.warn(f"{path.name} está bloqueado (intento {attempt}/{REPLACE_ATTEMPTS}); nuevo intento en {REPLACE_BACKOFF_SECONDS * attempt:.0f} s.")
                time.sleep(REPLACE_BACKOFF_SECONDS * attempt)

    def _sqlite_values(self, frame):
        converted = {}
        for column, dtype in frame.dtypes.items():
            kind = logical_type(dtype)
            series = frame[column]
            if kind in ("date", "timestamp"):
                converted[column] = [None if pd.isna(value) else (value.isoformat() if hasattr(value, "isoformat") else str(value)) for value in series]
            elif kind == "bool":
                converted[column] = [None if pd.isna(value) else int(bool(value)) for value in series]
            elif kind == "int":
                converted[column] = [None if pd.isna(value) else int(value) for value in series]
            elif kind == "float":
                converted[column] = [None if pd.isna(value) else float(value) for value in series]
            else:
                converted[column] = [None if pd.isna(value) else str(value) for value in series]
        return list(zip(*converted.values()))

    def _write_csv(self, frames):
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        counts = {}
        for name, frame in frames.items():
            path = self.csv_dir / f"{name}.csv"
            temporary = path.with_suffix(".csv.tmp")
            frame.to_csv(temporary, index=False, encoding="utf-8-sig")
            self._replace(temporary, path)
            counts[name] = len(pd.read_csv(path, encoding="utf-8-sig", usecols=[0]))
        return counts

    def _write_postgres(self, frames):
        self.postgres_dir.mkdir(parents=True, exist_ok=True)
        schema = self.postgres_schema
        ddl = [
            "-- DDL generado por el pipeline (src/serving/esquema_relacional.py). No lo edite a mano.",
            "-- Crea el esquema relacional de la capa Oro en PostgreSQL con claves primarias y foráneas.",
            f"DROP SCHEMA IF EXISTS {schema} CASCADE;",
            f"CREATE SCHEMA {schema};",
            "",
        ]
        ddl += [create_table(name, frame, POSTGRES_TYPES, schema) + "\n" for name, frame in frames.items()]
        ddl += [f"CREATE VIEW {schema}.{name} AS {query.replace('FROM ', f'FROM {schema}.').replace('JOIN ', f'JOIN {schema}.')};\n" for name, query in VIEWS.items()]
        load = [
            "-- Carga de los CSV de data/serving/csv en PostgreSQL con psql (ejecutar desde la raíz del repositorio):",
            "--   psql \"$DATABASE_URL\" -f data/serving/postgresql/01_ddl.sql",
            "--   psql \"$DATABASE_URL\" -f data/serving/postgresql/02_carga.sql",
            "SET client_encoding = 'UTF8';",
        ]
        load += [f"\\copy {schema}.{name} ({', '.join(frame.columns)}) FROM 'data/serving/csv/{name}.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');" for name, frame in frames.items()]
        paths = [self.postgres_dir / "01_ddl.sql", self.postgres_dir / "02_carga.sql"]
        for path, lines in zip(paths, (ddl, load)):
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return paths

    def _manifest(self, run_id, started_at, sources, outputs, counts):
        payloads = []
        for path in outputs:
            with path.open("rb") as file:
                sha256 = hashlib.file_digest(file, "sha256").hexdigest()
            payloads.append({"dataset": path.stem, "path": self.manifest.relative_path(path), "sha256": sha256, "size_bytes": path.stat().st_size})
        return {
            "run_id": run_id,
            "status": "completada",
            "started_at_utc": started_at.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "quality_report": f"{run_id}.quality.json",
            "inputs": [{"dataset": name, "run_id": source["run_id"], "manifest": source["manifest"], "sha256": source["sha256"]} for name, source in sources.items()],
            "filas_sqlite": counts["tables"],
            "payloads": payloads,
        }
