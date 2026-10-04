import pandas as pd


class PoblacionConsolidator:
    def __init__(self, source_config, silver_config):
        self.source_tables = source_config["tables"]
        self.overlap = source_config["reconciliation"]["migration_overlap"]
        self.silver_tables = silver_config["tables"]
        self.annual_reference = silver_config["annual_reference"]

    def consolidate(self, frame):
        frame = self._annual(frame)
        frame = self._migration_overlap(frame)
        frame = self._excluded_scenarios(frame)
        return self._deduplicated(frame).reset_index(drop=True)

    def _annual(self, frame):
        subannual_tables = [
            table_id for table_id, table in self.source_tables.items() if table["native_frequency"] != "anual"
        ]
        subannual = frame["tabla_id"].isin(subannual_tables)
        fecha = frame["fecha_referencia"]
        at_reference = fecha.dt.month.eq(self.annual_reference["month"]) & fecha.dt.day.eq(self.annual_reference["day"])
        misplaced = ~subannual & ~at_reference
        if misplaced.any():
            tables = sorted(frame.loc[misplaced, "tabla_id"].unique())
            raise ValueError(f"Las tablas anuales {tables} tienen fechas distintas de la fecha de referencia anual configurada.")
        return frame[~subannual | at_reference.astype(bool)]

    def _migration_overlap(self, frame):
        superseded = frame["tabla_id"].eq(self.overlap["non_preferred_table_id"]) & frame["anyo"].ge(self.overlap["period"])
        return frame[~superseded]

    def _excluded_scenarios(self, frame):
        excluded_pairs = [
            (table_id, scenario)
            for table_id, table in self.silver_tables.items()
            for scenario in table.get("excluded_scenarios", [])
        ]
        pairs = pd.MultiIndex.from_frame(frame[["tabla_id", "escenario"]].astype(object))
        return frame[~pairs.isin(excluded_pairs)]

    def _deduplicated(self, frame):
        duplicated_tables = [
            table_id
            for table_id, table in self.source_tables.items()
            if table.get("source_behavior", {}).get("duplicate_series_response")
        ]
        copies = frame["tabla_id"].isin(duplicated_tables) & frame.duplicated(keep="first")
        return frame[~copies]
