from pathlib import Path
import hashlib
import json

from src.utils.run_manifest import RunManifest
from fakes.ine_payloads import load_config

DATASET_IDS = ("pib", "gasto_pensiones", "poblacion_control")
UPDATED = "2026-09-29T11:00:00+0200"


def jsonstat(dimensions, values, status=None, updated=UPDATED):
    """dimensions: lista de (id, [códigos]); values: {posición: valor} en orden row-major."""
    return {
        "version": "2.0",
        "class": "dataset",
        "label": "Conjunto de prueba",
        "updated": updated,
        "id": [name for name, _ in dimensions],
        "size": [len(codes) for _, codes in dimensions],
        "dimension": {name: {"category": {"index": {code: position for position, code in enumerate(codes)}}} for name, codes in dimensions},
        "value": {str(position): value for position, value in values.items()},
        "status": {str(position): flag for position, flag in (status or {}).items()},
    }


def no_flag(metric, year):
    return None


def series_payload(fixed, metric_dimension, metric_codes, years, value_of, status_of=no_flag):
    dimensions = [("freq", ["A"]), *[(name, [code]) for name, code in fixed], (metric_dimension, list(metric_codes)), ("geo", ["ES"]), ("time", [str(year) for year in years])]
    values, status = {}, {}
    for metric_position, metric in enumerate(metric_codes):
        for year_position, year in enumerate(years):
            position = metric_position * len(years) + year_position
            values[position] = value_of(metric, year)
            flag = status_of(metric, year)
            if flag:
                status[position] = flag
    return jsonstat(dimensions, values, status)


def gdp(year):
    return 1_000_000.0 + (year - 1995) * 10_000


def pension_spending(year):
    return 120_000.0 + (year - 1995) * 1_000


def default_payloads(pib_years=range(1995, 2026), pension_years=range(1995, 2025), population_years=range(1971, 2026)):
    pib = series_payload(
        [("na_item", "B1GQ")], "unit", ["CP_MEUR"], list(pib_years),
        lambda metric, year: gdp(year),
        lambda metric, year: "p" if year >= 2023 else None,
    )
    pensions = series_payload(
        [("spdepb", "TOTAL"), ("spdepm", "TOTAL")], "unit", ["MIO_EUR", "PC_GDP"], list(pension_years),
        lambda metric, year: pension_spending(year) if metric == "MIO_EUR" else round(pension_spending(year) / gdp(year) * 100, 2),
    )
    population = series_payload(
        [("age", "TOTAL"), ("sex", "T")], "unit", ["NR"], list(population_years),
        lambda metric, year: 40_000_000 + (year - 1971) * 100_000,
    )
    return {"pib": pib, "gasto_pensiones": pensions, "poblacion_control": population}


def eurostat_config(root, config=None):
    config = config or load_config()
    bronze = root / "data" / "bronze" / "eurostat"
    silver = root / "data" / "silver" / "macro"
    config["sources"]["eurostat"]["storage"] = {
        "payloads_path": str(bronze),
        "manifests_path": str(bronze / "manifests"),
        "unmanifested_path": str(bronze / "_sin_manifiesto"),
    }
    config["silver"]["eurostat"]["output_path"] = str(silver)
    config["silver"]["eurostat"]["manifests_path"] = str(silver / "manifests")
    return config


class FakeEurostatBronze:
    def __init__(self, config):
        storage = config["sources"]["eurostat"]["storage"]
        self.root = Path(storage["payloads_path"])
        self.manifest = RunManifest(storage["manifests_path"])

    def run(self, run_id, started_at, payloads=None, status="completada"):
        payloads = default_payloads() if payloads is None else payloads
        self.root.mkdir(parents=True, exist_ok=True)
        entries = []
        for dataset_id, payload in payloads.items():
            content = json.dumps(payload).encode("utf-8")
            path = self.root / f"{dataset_id}_{run_id}.json"
            path.write_bytes(content)
            entries.append(
                {
                    "dataset_id": dataset_id,
                    "source_updated": payload.get("updated"),
                    "path": self.manifest.relative_path(path),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            )
        self.manifest.write({"run_id": run_id, "status": status, "started_at_utc": started_at, "payloads": entries})
        return entries
