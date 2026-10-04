from pathlib import Path
import json

import yaml

from fakes.fake_response import FakeResponse

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
TABLE_ID = "56934"
AGE_GROUP_ID = 113325
SEX_GROUP_ID = 113326
PAYLOADS = {
    "detalle": '[{"COD": "ECP1", "Nombre": "Total Nacional. 0 años.", "Data": [{"Anyo": 2025, "Valor": 1.0}]}]\r\n'.encode("utf-8"),
    "total_edad": b'[{"COD":"ECP320","Data":[{"Anyo":2025,"Valor":49128297.0}]}]',
    "semiintervalos_edad": b'[{"COD":"ECP9","Data":[{"Anyo":1971,"Valor":187261.0}]},{"COD":"ECP10","Data":[]}]',
}


class IneCatalog:
    def __init__(self, tmp_path):
        with CONFIG_PATH.open(encoding="utf-8") as file:
            self.config = yaml.safe_load(file)["sources"]["ine"]
        self.config["base_url"] = "https://ine.test"
        self.config["storage"]["payloads_path"] = str(tmp_path / "ine")
        self.config["storage"]["manifests_path"] = str(tmp_path / "ine" / "manifests")
        self.payloads_path = tmp_path / "ine"
        self.manifests_path = tmp_path / "ine" / "manifests"
        self.base_url = "https://ine.test/ES"
        self.data_url = f"{self.base_url}/DATOS_TABLA/{TABLE_ID}"
        self.groups = [
            {"Id": AGE_GROUP_ID, "Nombre": "Edad simple"},
            {"Id": SEX_GROUP_ID, "Nombre": "Sexo"},
        ]
        self.values = {
            SEX_GROUP_ID: [
                {"Id": 451, "FK_Variable": 18, "Nombre": "Total"},
                {"Id": 452, "FK_Variable": 18, "Nombre": "Hombres"},
                {"Id": 453, "FK_Variable": 18, "Nombre": "Mujeres"},
            ],
            AGE_GROUP_ID: self._age_values(),
        }
        self.variables = {
            355: {"Id": 355, "Nombre": "Valores simples de edad"},
            356: {"Id": 356, "Nombre": "Totales de edad"},
            357: {"Id": 357, "Nombre": "Semiintervalos de edad"},
        }

    def table_filters(self):
        return self.config["tables"][TABLE_ID]["filters"]

    def control_filters(self, index):
        return self.config["tables"][TABLE_ID]["control_queries"][index]["filters"]

    def successful_events(self):
        return [self.data_response(content, query_name) for query_name, content in PAYLOADS.items()]

    def routes(self, data_events):
        routes = {
            f"{self.base_url}/GRUPOS_TABLA/{TABLE_ID}": [self._json_response(self.groups)],
            f"{self.base_url}/VALORES_GRUPOSTABLA/{TABLE_ID}/{AGE_GROUP_ID}": [self._json_response(self.values[AGE_GROUP_ID])],
            f"{self.base_url}/VALORES_GRUPOSTABLA/{TABLE_ID}/{SEX_GROUP_ID}": [self._json_response(self.values[SEX_GROUP_ID])],
            self.data_url: list(data_events),
        }
        for variable_id, variable in self.variables.items():
            routes[f"{self.base_url}/VARIABLE/{variable_id}"] = [self._json_response(variable)]
        return routes

    def data_response(self, content, query_name):
        return FakeResponse(200, content, f"{self.data_url}?consulta={query_name}")

    def _age_values(self):
        values = [{"Id": 15668, "FK_Variable": 356, "Nombre": "Todas las edades"}]
        values.extend({"Id": 15319 + age, "FK_Variable": 355, "Nombre": f"{age} años"} for age in range(105))
        values.extend(
            [
                {"Id": 15100, "FK_Variable": 357, "Nombre": "85 y más años"},
                {"Id": 15071, "FK_Variable": 357, "Nombre": "100 y más años"},
                {"Id": 311059, "FK_Variable": 357, "Nombre": "105 y más años"},
            ]
        )
        return values

    def _json_response(self, content):
        return FakeResponse(200, json.dumps(content, ensure_ascii=False).encode("utf-8"), self.base_url)
