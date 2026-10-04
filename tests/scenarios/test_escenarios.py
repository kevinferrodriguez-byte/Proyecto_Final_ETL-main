from pathlib import Path

import pandas as pd

from src.quality.escenarios_quality import EscenariosQuality
from src.quality.quality_evaluation import QualityEvaluation
from src.scenarios.proyecciones import Proyecciones


def outputs(built_pipeline):
    return {name: pd.read_parquet(path) for name, path in built_pipeline["results"]["escenarios"]["paths"].items()}


def model_dimensions(built_pipeline):
    return {name: pd.read_parquet(path) for name, path in built_pipeline["results"]["modelo"]["paths"].items() if name.startswith("dim_")}


def layer(built_pipeline):
    frames = outputs(built_pipeline)
    dimensions = {**model_dimensions(built_pipeline), "dim_escenario": frames["dim_escenario"]}
    return {
        "dimensions": dimensions,
        "fact": frames["fact_proyecciones_demograficas"],
        "mart": frames["dm_escenarios_2050"],
        "schemas": Proyecciones(built_pipeline["config"]).schemas,
        "expected_rows": {"total": len(frames["fact_proyecciones_demograficas"])},
        "scenarios_present": sorted(frames["dim_escenario"]["codigo_escenario"]),
    }


def failed(evaluation):
    return sorted(rule["regla"] for rule in evaluation.rules if rule["resultado"] == "falla")


def test_scenarios_layer_only_holds_official_demographic_projections(built_pipeline):
    frames = outputs(built_pipeline)
    fact = frames["fact_proyecciones_demograficas"]
    indicators = model_dimensions(built_pipeline)["dim_indicador"].set_index("indicador_key")

    assert set(fact["estado_dato"]) == {"proyectado"}
    assert set(indicators.loc[fact["indicador_key"].unique(), "dominio"]) == {"demografia"}
    assert set(frames["dim_escenario"]["codigo_escenario"]) == {"central", "fecundidad_alta"}
    assert frames["dim_escenario"]["alcance"].str.contains("No es un escenario fiscal").all()


def test_scenario_fact_reuses_the_conformed_dimensions_of_the_model(built_pipeline):
    fact = outputs(built_pipeline)["fact_proyecciones_demograficas"]
    dimensions = model_dimensions(built_pipeline)

    assert set(fact["tiempo_key"]) <= set(dimensions["dim_tiempo"]["tiempo_key"])
    assert set(fact["indicador_key"]) <= set(dimensions["dim_indicador"]["indicador_key"])
    assert dimensions["dim_tiempo"].set_index("anyo").loc[2030, "es_proyeccion"]


def test_mart_compares_each_scenario_with_base_and_with_the_last_observed_year(built_pipeline):
    mart = outputs(built_pipeline)["dm_escenarios_2050"]

    assert (mart.loc[mart["escenario_kr"].eq("base"), "diferencia_vs_base"] == 0).all()
    ageing = mart[mart["indicador"].eq("indice_envejecimiento")].iloc[0]
    assert ageing["anyo_ultimo_observado"] == 2020
    assert ageing["variacion_vs_ultimo_observado"] == ageing["valor"] - ageing["valor_ultimo_observado"]


def test_published_layer_passes_and_tampering_is_detected(built_pipeline):
    quality = EscenariosQuality(built_pipeline["config"])
    assert quality.evaluate(layer(built_pipeline), QualityEvaluation()).passed()

    tampered = layer(built_pipeline)
    tampered["fact"].loc[0, "escenario_key"] = 99
    assert "fact_fk_validas" in failed(quality.evaluate(tampered, QualityEvaluation()))

    incoherent = layer(built_pipeline)
    indicators = incoherent["dimensions"]["dim_indicador"].set_index("codigo_indicador")["indicador_key"]
    mask = incoherent["fact"]["indicador_key"].eq(indicators["tasa_dependencia"])
    incoherent["fact"].loc[mask, "valor"] += 5
    assert "coherencia" in failed(quality.evaluate(incoherent, QualityEvaluation()))


def test_scenarios_manifest_declares_no_own_modelling(built_pipeline):
    import json

    manifest = json.loads(Path(built_pipeline["results"]["escenarios"]["manifest_path"]).read_text(encoding="utf-8"))
    assert "no contiene modelación propia" in manifest["nota"]
