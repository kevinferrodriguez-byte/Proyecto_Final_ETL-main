import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from src.model.dimensiones import Dimensiones
from src.model.hechos import Hechos
from src.model.modelo_gold import DIMENSIONS, FACT, PANEL, ModeloGold
from src.model.panel import Panel
from src.quality.modelo_quality import ModeloQuality
from src.quality.quality_evaluation import QualityEvaluation
from fakes.pipeline_context import reset_app_logger


def load_model(built_pipeline):
    paths = {name: Path(path) for name, path in built_pipeline["results"]["modelo"]["paths"].items()}
    frames = {name: pd.read_parquet(path) for name, path in paths.items()}
    config = built_pipeline["config"]
    dimensions_builder = Dimensiones(config)
    schemas = {**dimensions_builder.schemas, FACT: Hechos(config).schema, PANEL: Panel(config).schema}
    macro = pd.read_parquet(built_pipeline["root"] / "data" / "silver" / "macro" / "stg_macro_anual.parquet")
    return {
        "dimensions": {name: frames[name] for name in DIMENSIONS},
        "fact": frames[FACT],
        "panel": frames[PANEL],
        "schemas": schemas,
        "expected_rows": {"total": len(frames[FACT])},
        "control_population": macro[macro["metrica"].eq("poblacion_1_enero")][["anyo", "valor"]],
    }


def failed(evaluation):
    return sorted(rule["regla"] for rule in evaluation.rules if rule["resultado"] == "falla")


def evaluate(built_pipeline, model):
    return ModeloQuality(built_pipeline["config"]).evaluate(model, QualityEvaluation())


def test_published_model_passes_every_rule(built_pipeline):
    evaluation = evaluate(built_pipeline, load_model(built_pipeline))

    assert evaluation.passed(), evaluation.problems()
    assert evaluation.metrics["completitud_temporal_minima"] == 1.0


def test_model_contains_only_observed_data_and_the_eight_kpis(built_pipeline):
    model = load_model(built_pipeline)
    indicators = model["dimensions"]["dim_indicador"]

    assert set(model["fact"]["estado_dato"]) <= {"observado", "provisional"}
    kpis = indicators[indicators["tipo_indicador"].eq("kpi")].sort_values("codigo_kpi")
    assert kpis["codigo_kpi"].tolist() == [f"KPI-0{number}" for number in range(1, 9)]
    assert set(kpis["indicador_key"]) <= set(model["fact"]["indicador_key"])


def test_dimension_keys_are_deterministic_across_runs(built_pipeline, tmp_path):
    config = copy.deepcopy(built_pipeline["config"])
    config["modelo"]["output_path"] = str(tmp_path / "modelo")
    config["modelo"]["manifests_path"] = str(tmp_path / "modelo" / "manifests")
    first = load_model(built_pipeline)["dimensions"]
    try:
        again = ModeloGold(config).run()
    finally:
        reset_app_logger()
    for name in ("dim_indicador", "dim_sexo", "dim_grupo_edad", "dim_fuente", "dim_territorio", "dim_tiempo"):
        pd.testing.assert_frame_equal(first[name], pd.read_parquet(again["paths"][name]))


def test_duplicated_fact_row_is_rejected(built_pipeline):
    model = load_model(built_pipeline)
    model["fact"] = pd.concat([model["fact"], model["fact"].iloc[[0]]], ignore_index=True)

    assert {"fact_clave_unica", "fact_filas_conservadas"} <= set(failed(evaluate(built_pipeline, model)))


def test_orphan_foreign_key_is_rejected(built_pipeline):
    model = load_model(built_pipeline)
    model["fact"].loc[0, "indicador_key"] = 999

    assert "fact_fk_validas" in failed(evaluate(built_pipeline, model))


def test_out_of_range_value_is_rejected(built_pipeline):
    model = load_model(built_pipeline)
    indicators = model["dimensions"]["dim_indicador"].set_index("codigo_indicador")["indicador_key"]
    model["fact"].loc[model["fact"]["indicador_key"].eq(indicators["indicador_coyuntural_fecundidad"]), "valor"] = 9.0

    assert "fact_rangos_validos" in failed(evaluate(built_pipeline, model))


def test_kpi_inconsistent_with_its_components_is_rejected(built_pipeline):
    model = load_model(built_pipeline)
    indicators = model["dimensions"]["dim_indicador"].set_index("codigo_indicador")["indicador_key"]
    mask = model["fact"]["indicador_key"].eq(indicators["ratio_cotizantes_pensionistas"])
    model["fact"].loc[mask, "valor"] = model["fact"].loc[mask, "valor"] * 1.01

    rules = failed(evaluate(built_pipeline, model))
    assert "fact_coherencia" in rules and "panel_conciliado" in rules


def test_projected_row_in_the_model_is_rejected(built_pipeline):
    model = load_model(built_pipeline)
    model["fact"]["estado_dato"] = model["fact"]["estado_dato"].astype(object)
    model["fact"].loc[0, "estado_dato"] = "proyectado"
    model["fact"]["estado_dato"] = model["fact"]["estado_dato"].astype("string")

    assert failed(evaluate(built_pipeline, model)) == ["fact_esquema"]


def test_panel_has_one_row_per_year_and_matches_the_fact_table(built_pipeline):
    model = load_model(built_pipeline)
    panel = model["panel"]

    assert not panel.duplicated(["tiempo_key", "territorio_key"]).any()
    assert panel.loc[panel["anyo"].eq(2020), "poblacion_total"].iloc[0] == 34.0
    assert panel.loc[panel["anyo"].eq(2024), "tiene_datos_provisionales"].iloc[0]


def test_model_manifest_links_every_input(built_pipeline):
    manifest = json.loads(Path(built_pipeline["results"]["modelo"]["manifest_path"]).read_text(encoding="utf-8"))

    assert {item["dataset"] for item in manifest["inputs"]} == {
        "stg_poblacion_anual",
        "stg_afiliados_mensual",
        "stg_macro_anual",
        "kpis_demograficos",
        "kpi_ratio_sostenibilidad_anual",
        "kpis_integrados_anual",
    }
    assert {"ine_1", "seguridad_social_1", "eurostat_1"} <= set(manifest["bronze_run_ids"])


def test_stale_indicators_break_the_lineage_check(built_pipeline):
    config = built_pipeline["config"]
    gold = ModeloGold(config)
    inputs = {name: reader.latest() for name, reader in gold.readers.items()}
    inputs["kpis_demograficos"]["frame"] = inputs["kpis_demograficos"]["frame"].assign(silver_run_id="silver_antiguo")

    problems = gold._lineage(inputs)

    assert any("kpis_demograficos procede de Plata" in problem for problem in problems)


@pytest.mark.parametrize("column", ["tiempo_key", "valor"])
def test_null_in_a_mandatory_fact_column_breaks_the_schema(built_pipeline, column):
    model = load_model(built_pipeline)
    model["fact"][column] = model["fact"][column].astype("float64")
    model["fact"].loc[0, column] = float("nan")

    assert "fact_esquema" in failed(evaluate(built_pipeline, model))
