import pandas as pd

from src.model.modelo_schema import TOTAL_AGE_GROUP, PanelSchema

POPULATION_COLUMNS = {
    TOTAL_AGE_GROUP: "poblacion_total",
    "menores_16": "poblacion_menores_16",
    "activos_16_64": "poblacion_16_64",
    "mayores_65": "poblacion_65_mas",
}


class Panel:
    """dm_panel_anual: vista ancha y desnormalizada de fact_indicadores_anual para sexo total.

    Es el conjunto consolidado para Power BI o para análisis exploratorio: una fila por año y territorio y una
    columna por indicador. No contiene cálculos propios: cada celda es una fila de la tabla de hechos (la regla
    `panel_conciliado` lo verifica). Una celda vacía significa que la fuente no publica ese año.
    """

    def __init__(self, config):
        self.indicators = [code for code, _ in sorted(config["modelo"]["indicators"].items(), key=lambda item: item[1]["key"]) if code != "poblacion"]
        self.value_columns = list(POPULATION_COLUMNS.values()) + self.indicators
        self.schema = PanelSchema(tuple(self.value_columns))

    def build(self, fact, dimensions, gold_run_id):
        wide = self.denormalize(fact, dimensions)
        wide = wide[wide["codigo_sexo"].eq("total")]
        population = wide[wide["codigo_indicador"].eq("poblacion")].pivot_table(
            index=["tiempo_key", "territorio_key"], columns="codigo_grupo", values="valor", aggfunc="first"
        )
        population = population.reindex(columns=list(POPULATION_COLUMNS)).rename(columns=POPULATION_COLUMNS)
        totals = wide[wide["codigo_grupo"].eq(TOTAL_AGE_GROUP) & wide["codigo_indicador"].ne("poblacion")]
        indicators = totals.pivot_table(index=["tiempo_key", "territorio_key"], columns="codigo_indicador", values="valor", aggfunc="first")
        indicators = indicators.reindex(columns=self.indicators)
        provisional = wide.assign(provisional=wide["estado_dato"].eq("provisional")).groupby(["tiempo_key", "territorio_key"])["provisional"].any()
        panel = population.join(indicators, how="outer").join(provisional.rename("tiene_datos_provisionales"), how="left").reset_index()
        panel["anyo"] = panel["tiempo_key"]
        panel["tiene_datos_provisionales"] = panel["tiene_datos_provisionales"].fillna(False).astype(bool)
        panel["gold_run_id"] = gold_run_id
        panel = panel[self.schema.columns()].astype(self.schema.dtypes)
        return panel.sort_values(["territorio_key", "anyo"], ignore_index=True)

    def denormalize(self, fact, dimensions):
        frame = fact.merge(dimensions["dim_sexo"][["sexo_key", "codigo_sexo"]], on="sexo_key", how="left")
        frame = frame.merge(dimensions["dim_grupo_edad"][["grupo_edad_key", "codigo_grupo"]], on="grupo_edad_key", how="left")
        frame = frame.merge(dimensions["dim_indicador"][["indicador_key", "codigo_indicador"]], on="indicador_key", how="left")
        return frame.merge(dimensions["dim_tiempo"][["tiempo_key", "anyo"]], on="tiempo_key", how="left")

