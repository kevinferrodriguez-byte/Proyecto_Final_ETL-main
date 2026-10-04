from src.extract.ine.ine_endpoints import IneEndpoints
from src.extract.http_client import HttpClient
import json


class IneApi:
    def __init__(self, config):
        self.endpoints = IneEndpoints(config)
        self.http = HttpClient(config["request"])
        self.data_parameters = dict(config["data_parameters"])

    def groups(self, table_id):
        url = self.endpoints.groups_table(table_id)
        return self._metadata_list(url, f"Los grupos de la tabla INE {table_id}")

    def group_values(self, table_id, group_id):
        url = self.endpoints.group_values(table_id, group_id)
        return self._metadata_list(url, f"Los valores del grupo {group_id} de la tabla INE {table_id}")

    def variable(self, variable_id):
        description = f"Los metadatos de la variable INE {variable_id}"
        variable = self._parse(self.http.get(self.endpoints.variable(variable_id)).content, description)
        if not isinstance(variable, dict) or "Nombre" not in variable:
            raise ValueError(f"{description} no tienen el formato esperado.")
        return variable

    def table_data(self, table_id, tv_filters):
        url = self.endpoints.data_table(table_id)
        response = self.http.get(url, [("tv", value) for value in tv_filters] + list(self.data_parameters.items()))
        series = self._parse(response.content, f"La respuesta de datos de la tabla INE {table_id}")
        return {"response": response, "validations": self._validate_data(table_id, series)}

    def close(self):
        self.http.close()

    def _metadata_list(self, url, description):
        content = self._parse(self.http.get(url).content, description)
        if not isinstance(content, list) or not content:
            raise ValueError(f"{description} no tienen el formato esperado o están vacíos.")
        return content

    def _parse(self, content, description):
        if not content or content.isspace():
            raise ValueError(f"{description} llegó vacía; no se guarda ningún archivo.")
        try:
            return json.loads(content)
        except ValueError as error:
            raise ValueError(f"{description} no es JSON válido; no se guarda ningún archivo.") from error

    def _validate_data(self, table_id, series):
        if not isinstance(series, list) or not series:
            raise ValueError(f"La tabla INE {table_id} no devolvió series para los filtros solicitados. Revise los filtros en config/config.yaml.")
        observation_count = sum(len(item.get("Data") or []) for item in series if isinstance(item, dict))
        if observation_count == 0:
            raise ValueError(f"La tabla INE {table_id} devolvió series sin datos; no se guarda ningún archivo.")
        return {
            "json_valid": True,
            "series_present": True,
            "data_present": True,
            "metadata_present": all(isinstance(item, dict) and item.get("MetaData") for item in series),
            "series_count": len(series),
            "observation_count": observation_count,
        }
