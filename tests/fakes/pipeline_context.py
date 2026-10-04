import logging

import yaml

from src.logger import APP_LOGGER_NAME
from fakes.fake_bronze import FakeBronze, minimal_payloads
from fakes.fake_eurostat import FakeEurostatBronze
from fakes.fake_seguridad_social import FakeSeguridadSocialBronze
from fakes.fake_silver import FakeSilver
from fakes.ine_payloads import load_config

# Cobertura (años observados) de los datos sintéticos: sustituye a la del catálogo real en las pruebas.
FAKE_COVERAGE = {
    "poblacion": (2020, 2020),
    "indice_envejecimiento": (2020, 2020),
    "tasa_dependencia": (2020, 2020),
    "tasa_dependencia_mayores": (2020, 2020),
    "porcentaje_mayores_65": (2020, 2020),
    "nacimientos": (2020, 2020),
    "defunciones": (2020, 2020),
    "saldo_vegetativo": (2020, 2020),
    "saldo_migratorio_exterior": (2020, 2021),
    "indicador_coyuntural_fecundidad": (2020, 2020),
    "esperanza_vida_nacimiento": (2020, 2020),
    "esperanza_vida_65": (2020, 2020),
    "total_afiliados": (2016, 2025),
    "tasa_afiliacion_16_64": (2019, 2019),
    "total_pensiones": (2016, 2025),
    "ratio_cotizantes_pensionistas": (2016, 2025),
    "importe_nomina_pensiones": (2016, 2025),
    "pension_media_mensual": (2016, 2025),
    "pib": (1995, 2025),
    "gasto_pensiones": (1995, 2024),
    "gasto_pensiones_pib": (1995, 2024),
}
INE_PERIODS = {"56934": (2020, 2020), "6566": (2020, 2020), "24309": (2020, 2020), "69758": (2021, 2021), "36643": (2030, 2030), "36652": (2030, 2030)}


def reset_app_logger():
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    for handler in list(app_logger.handlers):
        app_logger.removeHandler(handler)
        handler.close()
    app_logger.setLevel(logging.NOTSET)
    app_logger.propagate = True


def redirect_paths(node, root):
    """Reescribe toda ruta relativa del repositorio (data/..., logs/...) bajo el directorio temporal."""
    if isinstance(node, dict):
        return {key: redirect_paths(value, root) for key, value in node.items()}
    if isinstance(node, list):
        return [redirect_paths(value, root) for value in node]
    if isinstance(node, str) and (node.startswith("data/") or node.startswith("logs")):
        return str(root / node)
    return node


class PipelineContext:
    """Configuración real apuntando a un directorio temporal, con dobles de Bronce para las tres fuentes."""

    def __init__(self, root):
        self.root = root
        self.config = redirect_paths(load_config(), root)
        self.bronze = FakeBronze(root / "data" / "bronze" / "ine")
        self.silver = FakeSilver(root / "data" / "silver")
        self.social = FakeSeguridadSocialBronze(self.config)
        self.eurostat = FakeEurostatBronze(self.config)
        self.config["silver"]["seguridad_social"]["afiliados"]["periods"]["expected_start"] = "2016-01"
        # Escala de edades mínima (0 | 1-2 | 3+) para que 4 edades formen los tres grupos.
        self.config["silver"]["ine"]["homologated_top_age"] = 3
        self.config["indicadores"]["demografia"]["age_groups"] = {"young_max_age": 0, "working_min_age": 1, "working_max_age": 2, "elderly_min_age": 3}
        for table_id, (start, end) in INE_PERIODS.items():
            self.config["sources"]["ine"]["tables"][table_id]["periods"].update({"expected_start": start, "expected_end": end})
        for indicator, (start, end) in FAKE_COVERAGE.items():
            self.config["modelo"]["indicators"][indicator]["cobertura"] = {"desde": start, "hasta": end}
        # La población sintética es de decenas de personas: la tasa de afiliación sale fuera del rango real.
        self.config["modelo"]["indicators"]["tasa_afiliacion_16_64"]["rango"] = {"min": 0, "max": 1e12}
        self.config["escenarios"]["mart"].update({"start_year": 2030, "end_year": 2030, "escenario_kr": ["base"]})

    def publish_bronze(self):
        self.bronze.run("ine_1", "2026-09-26T01:00:00.000000Z", minimal_payloads(sexes=("total", "hombres", "mujeres")))
        self.social.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z")
        self.eurostat.run("eurostat_1", "2026-09-26T01:00:00.000000Z")

    def runs(self):
        return sorted((self.root / "logs" / "ejecuciones").glob("pipeline_*.json"))

    def write_config(self):
        path = self.root / "config.yaml"
        path.write_text(yaml.safe_dump(self.config, allow_unicode=True), encoding="utf-8")
        return path
