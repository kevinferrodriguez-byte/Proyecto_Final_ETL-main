import hashlib
import json

from src.utils.run_manifest import RunManifest
from fakes.ine_payloads import births_deaths, fertility_1407, life_expectancy, migration_24309, migration_69758, point, population_series, projection_series

SEX_SHARES = {"total": 1.0, "hombres": 0.5, "mujeres": 0.5}


class FakeBronze:
    def __init__(self, root):
        self.root = root
        self.manifest = RunManifest(root / "manifests")

    def storage_config(self):
        return {
            "payloads_path": str(self.root),
            "manifests_path": str(self.root / "manifests"),
            "unmanifested_path": str(self.root / "_sin_manifiesto"),
        }

    def run(self, run_id, started_at, payloads, status="completada"):
        entries = []
        self.root.mkdir(parents=True, exist_ok=True)
        for key, series in payloads.items():
            content = json.dumps(series, ensure_ascii=False).encode("utf-8")
            path = self.root / f"{key[0]}_{key[1]}_{run_id}.json"
            path.write_bytes(content)
            entries.append(
                {
                    "table_id": key[0],
                    "query": key[1],
                    "path": self.manifest.relative_path(path),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            )
        self.manifest.write({"run_id": run_id, "status": status, "started_at_utc": started_at, "payloads": entries})
        return entries


def minimal_payloads(migration_2021=-1200.0, sexes=("total",)):
    """Bronce INE mínimo: población a 1/1/2020 (edades 0-2 y tramo abierto 3+), eventos 2020, IDB 2020 y proyección 2030.

    Con `sexes=("total", "hombres", "mujeres")` publica también la población por sexo (cada sexo, la mitad del total),
    que el modelo y la capa de escenarios necesitan para la regla «hombres + mujeres = total».
    """
    payloads = {("56934", "detalle"): [], ("56934", "total_edad"): [], ("56934", "semiintervalos_edad"): []}
    payloads.update({(table, query): [] for table in ("36643", "36652") for query in ("detalle", "total_edad")})
    for sex in sexes:
        share = SEX_SHARES[sex]
        payloads[("56934", "detalle")] += [
            population_series(f"ECP0{sex}", sex, "0 años", [point(2020, 10.0 * share), point(2020, 11.0 * share, month=7)]),
            population_series(f"ECP1{sex}", sex, "1 año", [point(2020, 9.0 * share), point(2020, 9.5 * share, month=7)]),
            population_series(f"ECP2{sex}", sex, "2 años", [point(2020, 8.0 * share), point(2020, 8.5 * share, month=7)]),
        ]
        payloads[("56934", "total_edad")].append(population_series(f"ECP320{sex}", sex, "Todas las edades", [point(2020, 34.0 * share), point(2020, 36.0 * share, month=7)]))
        payloads[("56934", "semiintervalos_edad")].append(population_series(f"ECP3{sex}", sex, "3 y más años", [point(2020, 7.0 * share), point(2020, 7.0 * share, month=7)]))
        payloads[("36643", "detalle")] += [
            projection_series(f"P{age}{sex}", sex, label, [point(2030, value * share)])
            for age, label, value in ((0, "0 años", 10.0), (1, "1 año", 9.0), (2, "2 años", 8.0), (3, "3 y más años", 7.0))
        ]
        payloads[("36643", "total_edad")].append(projection_series(f"PT{sex}", sex, "Todas las edades", [point(2030, 34.0 * share)]))
        payloads[("36652", "detalle")] += [
            projection_series(f"S{scenario}{age}{sex}", sex, label, [point(2030, value * share)], scenario)
            for scenario in ("Central", "Fecundidad alta")
            for age, label, value in ((0, "0 años", 10.0), (1, "1 año", 9.0), (2, "2 años", 8.0), (3, "3 y más años", 7.5))
        ]
        payloads[("36652", "total_edad")] += [
            projection_series(f"ST{scenario}{sex}", sex, "Todas las edades", [point(2030, 34.5 * share)], scenario) for scenario in ("Central", "Fecundidad alta")
        ]
    payloads.update(
        {
            ("6566", "detalle"): births_deaths({"Nacimiento": [point(2020, 340000.0)], "Defunción": [point(2020, 490000.0)]}) * 2,
            ("24309", "detalle"): migration_24309([point(2020, 210000.0), point(2021, 150000.0)]),
            ("69758", "detalle"): migration_69758([point(2021, migration_2021)]),
            ("1407", "detalle"): fertility_1407([point(2020, 1.19)]),
            ("1414", "detalle"): life_expectancy("1414", {"ambos": [point(2020, 82.3)], "hombres": [point(2020, 79.6)], "mujeres": [point(2020, 85.1)]}),
            ("1415", "detalle"): life_expectancy("1415", {"ambos": [point(2020, 19.7)], "hombres": [point(2020, 17.8)], "mujeres": [point(2020, 21.4)]}),
        }
    )
    return payloads
