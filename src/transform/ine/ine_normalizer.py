import pandas as pd

from src.transform.demografia_schema import DemografiaSchema

AGE_PATTERNS = {
    "simple": r"^(?P<edad>\d+) años?$",
    "tramo_abierto": r"^(?P<edad>\d+) y más años$",
    "total": r"^Todas las edades$",
}


class IneNormalizer:
    def __init__(self, source_config, silver_config):
        self.source_name = source_config["name"]
        self.source_tables = source_config["tables"]
        self.config = silver_config
        self.schema = DemografiaSchema()
        self.age_variables = {int(variable): age_type for variable, age_type in silver_config["variables"]["edad"].items()}
        self.units = {int(unit): name for unit, name in silver_config["units"].items()}

    def normalize(self, payload, series):
        table_id = payload["table_id"]
        table = self.config["tables"].get(table_id)
        if table is None:
            raise ValueError(f"La tabla INE {table_id} no tiene reglas en silver.ine.tables de config/config.yaml.")
        described = self._describe_series(table_id, table, series)
        observations = self._observations(table_id, series)
        frame = observations.merge(described, on="codigo_serie", how="left", validate="many_to_one")
        if len(frame) != len(observations) or frame["metrica"].isna().any():
            raise ValueError(f"La tabla INE {table_id} tiene observaciones sin serie descrita en MetaData.")
        missing = frame["valor"].isna() & frame["tipo_edad"].ne("simple")
        if missing.any():
            first = frame[missing].iloc[0]
            raise ValueError(
                f"La tabla INE {table_id} tiene {int(missing.sum())} valores nulos fuera de edades simples "
                f"(por ejemplo, serie {first['codigo_serie']}, año {first['anyo']}); solo pueden descartarse edades simples sin dato."
            )
        frame["fuente"] = self.source_name
        frame["tabla_id"] = table_id
        frame["consulta"] = payload["query"]
        frame["run_id"] = payload["run_id"]
        frame["estado_dato"] = self.source_tables[table_id]["data_state"]
        frame["es_control"] = payload["query"] != "detalle"
        return frame[self.schema.columns()].astype(self.schema.dtypes)

    def _describe_series(self, table_id, table, series):
        records = []
        for item in series:
            metadata = item.get("MetaData")
            if not metadata:
                raise ValueError(
                    f"La serie {item.get('COD')} de la tabla INE {table_id} no trae MetaData; "
                    "descargue Bronce con data_parameters.tip = M."
                )
            record = {"codigo_serie": item["COD"], "fk_unidad": item["FK_Unidad"]}
            for entry in metadata:
                column = f"v{entry['FK_Variable']}"
                if column in record:
                    raise ValueError(f"La serie {item['COD']} de la tabla INE {table_id} repite la variable {entry['FK_Variable']}.")
                record[column] = entry["Nombre"]
            records.append(record)
        described = pd.DataFrame(records).drop_duplicates()
        if described["codigo_serie"].duplicated().any():
            raise ValueError(f"La tabla INE {table_id} describe la misma serie con MetaData distinta.")
        self._check_variables(table_id, table, described)
        result = pd.DataFrame({"codigo_serie": described["codigo_serie"]})
        result["sexo"] = self._dimension(table_id, table, described, "sexo")
        result["territorio"] = self._dimension(table_id, table, described, "territorio")
        result["escenario"] = self._scenario(table_id, table, described)
        result["metrica"] = self._mapped(table_id, described[f"v{table['concept_variable']}"], table["concepts"], "concepto")
        result["unidad"] = self._mapped(table_id, described["fk_unidad"], self.units, "unidad (FK_Unidad)")
        return result.join(self._ages(table_id, table, described))

    def _check_variables(self, table_id, table, described):
        allowed = {
            self.config["variables"]["sexo"],
            self.config["variables"]["territorio"],
            table["concept_variable"],
            table.get("scenario_variable"),
        } | set(self.age_variables) | {int(variable) for variable in table["constant_variables"]}
        present = {int(column[1:]) for column in described.columns if column.startswith("v")}
        unknown = sorted(present - allowed)
        if unknown:
            raise ValueError(f"La tabla INE {table_id} trae variables no configuradas en MetaData: {unknown}.")
        for variable, labels in table["constant_variables"].items():
            column = described.get(f"v{variable}")
            if column is None or column.isna().any() or not column.isin(labels).all():
                raise ValueError(
                    f"La variable {variable} de la tabla INE {table_id} debe tomar solo los valores {labels} en todas las series."
                )

    def _dimension(self, table_id, table, described, name):
        column = described.get(f"v{self.config['variables'][name]}")
        implicit = name in table["implicit_dimensions"]
        if column is None and implicit:
            return self.config["implicit_dimensions"][name]
        if column is None or implicit:
            state = "falta" if column is None else "no debería aparecer"
            raise ValueError(f"La dimensión {name} {state} en la MetaData de la tabla INE {table_id}; revise implicit_dimensions.")
        return self._mapped(table_id, column, self.config["labels"][name], name)

    def _scenario(self, table_id, table, described):
        variable = table.get("scenario_variable")
        if variable is None:
            return table["escenario"]
        return self._mapped(table_id, described[f"v{variable}"], self.config["labels"]["escenario"], "escenario")

    def _mapped(self, table_id, column, mapping, name):
        mapped = column.map(mapping)
        unknown = sorted(set(column[mapped.isna()].astype(str)))
        if unknown:
            raise ValueError(f"Etiquetas de {name} desconocidas en la tabla INE {table_id}: {', '.join(unknown)}.")
        return mapped

    def _ages(self, table_id, table, described):
        if "edad" in table["implicit_dimensions"]:
            constants = {int(variable) for variable in table["constant_variables"]}
            if any(f"v{variable}" in described.columns for variable in self.age_variables if variable not in constants):
                raise ValueError(f"La tabla INE {table_id} trae edad en MetaData pero la declara implícita.")
            return pd.DataFrame(
                {
                    "tipo_edad": "total",
                    "edad_etiqueta_original": self.config["implicit_dimensions"]["edad_etiqueta"],
                    "edad_min": 0,
                    "edad_max": pd.NA,
                },
                index=described.index,
            )
        columns = [f"v{variable}" for variable in self.age_variables if f"v{variable}" in described.columns]
        labels = described[columns]
        if not labels.notna().sum(axis=1).eq(1).all():
            raise ValueError(f"Cada serie de la tabla INE {table_id} debe tener exactamente una variable de edad.")
        age_types = labels.notna().idxmax(axis=1).map({f"v{variable}": age_type for variable, age_type in self.age_variables.items()})
        label = labels.bfill(axis=1).iloc[:, 0]
        ages = pd.DataFrame({"tipo_edad": age_types, "edad_etiqueta_original": label})
        ages["edad_min"] = pd.Series(pd.NA, index=described.index, dtype="Int64")
        for age_type, pattern in AGE_PATTERNS.items():
            selected = age_types.eq(age_type)
            invalid = selected & ~label.str.fullmatch(pattern).fillna(False).astype(bool)
            if invalid.any():
                raise ValueError(
                    f"Etiquetas de edad no reconocidas como {age_type} en la tabla INE {table_id}: "
                    f"{', '.join(sorted(set(label[invalid])))}."
                )
            if age_type != "total":
                ages.loc[selected, "edad_min"] = label[selected].str.extract(pattern)["edad"].astype("Int64")
        ages.loc[age_types.eq("total"), "edad_min"] = 0
        ages["edad_max"] = ages["edad_min"].where(age_types.eq("simple"))
        return ages

    def _observations(self, table_id, series):
        observations = pd.json_normalize(series, record_path="Data", meta=["COD"]).rename(columns={"COD": "codigo_serie"})
        tipo_dato = {int(value) for value in observations["FK_TipoDato"].unique()}
        unexpected = sorted(tipo_dato - set(self.config["accepted_fk_tipo_dato"]))
        if unexpected:
            raise ValueError(
                f"La tabla INE {table_id} trae FK_TipoDato sin mapeo documentado: {unexpected}; "
                "revise silver.ine.accepted_fk_tipo_dato."
            )
        secret = observations["Secreto"].astype(bool)
        if secret.any():
            first = observations[secret].iloc[0]
            raise ValueError(
                f"La tabla INE {table_id} trae {int(secret.sum())} datos secretos (por ejemplo, serie {first['codigo_serie']}, "
                f"año {first['Anyo']}); el esquema de Plata no admite datos confidenciales."
            )
        fecha = pd.to_datetime(observations["Fecha"], unit="ms", utc=True).dt.tz_convert(self.config["timezone"])
        mismatched = fecha.dt.year.ne(observations["Anyo"])
        if mismatched.any():
            raise ValueError(f"La tabla INE {table_id} tiene {int(mismatched.sum())} observaciones cuyo Anyo no coincide con su Fecha.")
        return pd.DataFrame(
            {
                "codigo_serie": observations["codigo_serie"],
                "fecha_referencia": fecha.dt.date,
                "anyo": observations["Anyo"],
                "valor": pd.to_numeric(observations["Valor"], errors="raise"),
            }
        )
