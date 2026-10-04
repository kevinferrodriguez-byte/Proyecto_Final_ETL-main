from datetime import date

import pandas as pd

from src.model.modelo_schema import (
    OBSERVED_STATES,
    TOTAL_AGE_GROUP,
    DimFuenteSchema,
    DimGrupoEdadSchema,
    DimIndicadorSchema,
    DimSexoSchema,
    DimTerritorioSchema,
    DimTiempoSchema,
)

AGGREGATION_LEVELS = {"territorio": "territorio", "sexo": "sexo", "grupo_edad": "grupo de edad"}


class Dimensiones:
    """Dimensiones conformadas del modelo, compartidas por la capa de escenarios.

    Todas las claves son deterministas (salen del catálogo de configuración o del año), de modo que dos
    ejecuciones con los mismos datos producen las mismas claves y Power BI conserva las relaciones.
    """

    def __init__(self, config):
        model = config["modelo"]
        self.territories = model["territories"]
        self.sexes = model["sexes"]
        self.sources = model["sources"]
        self.indicators = model["indicators"]
        self.limits = config["indicadores"]["demografia"]["age_groups"]
        self.schemas = {
            "dim_tiempo": DimTiempoSchema(),
            "dim_territorio": DimTerritorioSchema(),
            "dim_sexo": DimSexoSchema(),
            "dim_grupo_edad": DimGrupoEdadSchema(),
            "dim_fuente": DimFuenteSchema(tuple(self.sources)),
            "dim_indicador": DimIndicadorSchema(tuple(self.indicators), tuple(self.sources)),
        }

    def build(self, facts, projected_years):
        return {
            "dim_tiempo": self.tiempo(facts, projected_years),
            "dim_territorio": self.territorio(facts["territorio"]),
            "dim_sexo": self.sexo(),
            "dim_grupo_edad": self.grupo_edad(),
            "dim_fuente": self.fuente(),
            "dim_indicador": self.indicador(),
        }

    def tiempo(self, facts, projected_years):
        observed_years = set(facts.loc[facts["estado_dato"].isin(OBSERVED_STATES), "anyo"].astype(int))
        projected_years = set(int(year) for year in projected_years)
        all_years = observed_years | projected_years
        years = list(range(min(all_years), max(all_years) + 1))
        schema = self.schemas["dim_tiempo"]
        frame = pd.DataFrame(
            {
                "tiempo_key": years,
                "anyo": years,
                "decada": [year // 10 * 10 for year in years],
                "fecha_inicio": pd.Series([date(year, 1, 1) for year in years], dtype=schema.dtypes["fecha_inicio"]),
                "fecha_fin": pd.Series([date(year, 12, 31) for year in years], dtype=schema.dtypes["fecha_fin"]),
                "es_observado": [year in observed_years for year in years],
                "es_proyeccion": [year in projected_years for year in years],
            }
        )
        return frame.astype(schema.dtypes)

    def territorio(self, codes):
        present = sorted(set(codes))
        unknown = [code for code in present if code not in self.territories]
        if unknown:
            raise ValueError(f"Territorios sin entrada en modelo.territories: {', '.join(unknown)}; añádalos al catálogo con una clave nueva.")
        rows = [
            {"territorio_key": self.territories[code]["key"], "codigo_territorio": code, "nombre_territorio": self.territories[code]["name"], "nivel_territorial": self.territories[code]["level"]}
            for code in present
        ]
        return pd.DataFrame(rows).sort_values("territorio_key", ignore_index=True).astype(self.schemas["dim_territorio"].dtypes)

    def sexo(self):
        rows = [{"sexo_key": spec["key"], "codigo_sexo": code, "nombre_sexo": spec["name"]} for code, spec in self.sexes.items()]
        return pd.DataFrame(rows).sort_values("sexo_key", ignore_index=True).astype(self.schemas["dim_sexo"].dtypes)

    def grupo_edad(self):
        young = self.limits["young_max_age"]
        working_min = self.limits["working_min_age"]
        working_max = self.limits["working_max_age"]
        elderly = self.limits["elderly_min_age"]
        rows = [
            (0, TOTAL_AGE_GROUP, 0, None, "Todas las edades"),
            (1, "menores_16", 0, young, f"De 0 a {young} años"),
            (2, "activos_16_64", working_min, working_max, f"De {working_min} a {working_max} años (edad de trabajar)"),
            (3, "mayores_65", elderly, None, f"{elderly} años y más (grupo abierto)"),
        ]
        frame = pd.DataFrame(rows, columns=["grupo_edad_key", "codigo_grupo", "edad_min", "edad_max", "descripcion"])
        return frame.astype(self.schemas["dim_grupo_edad"].dtypes)

    def fuente(self):
        rows = [{"fuente_key": spec["key"], "codigo_fuente": code, **{field: spec[field] for field in ("organismo", "acceso", "url", "conjuntos")}} for code, spec in self.sources.items()]
        return pd.DataFrame(rows).sort_values("fuente_key", ignore_index=True).astype(self.schemas["dim_fuente"].dtypes)

    def indicador(self):
        rows = []
        for code, spec in self.indicators.items():
            rows.append(
                {
                    "indicador_key": spec["key"],
                    "codigo_indicador": code,
                    "nombre_indicador": spec["nombre"],
                    "tipo_indicador": spec["tipo"],
                    "codigo_kpi": spec.get("codigo_kpi"),
                    "okr": spec["okr"],
                    "pestana_tablero": spec["pestana"],
                    "dominio": spec["dominio"],
                    "unidad": spec["unidad"],
                    "formula": spec["formula"],
                    "codigo_fuente": spec["fuente"],
                    "origen": spec["origen"],
                    "periodicidad": "anual",
                    "referencia_temporal": spec["referencia_temporal"],
                    "nivel_agregacion": "nacional por " + ", ".join(AGGREGATION_LEVELS[item] for item in spec["desagregaciones"]),
                    "cobertura_desde": spec["cobertura"]["desde"],
                    "cobertura_hasta": spec["cobertura"]["hasta"],
                    "rango_min": float(spec["rango"]["min"]),
                    "rango_max": float(spec["rango"]["max"]),
                    "sentido": spec["sentido"],
                    "descripcion": spec["descripcion"],
                }
            )
        return pd.DataFrame(rows).sort_values("indicador_key", ignore_index=True).astype(self.schemas["dim_indicador"].dtypes)
