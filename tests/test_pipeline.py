import json
from pathlib import Path

import pytest

import src.pipeline as pipeline_module
from src.pipeline import STAGES, Pipeline
from fakes.pipeline_context import PipelineContext, reset_app_logger

ALL_STEPS_FROM_SILVER = [
    "integridad_bronce",
    "plata_ine",
    "plata_seguridad_social",
    "plata_eurostat",
    "indicadores_demografia",
    "indicadores_pensiones",
    "indicadores_integrados",
    "modelo",
    "escenarios",
    "carga",
]


def run_pipeline(context, start, end=None):
    try:
        return Pipeline(context.config).run(start, end)
    finally:
        reset_app_logger()


def read_record(context):
    runs = context.runs()
    assert len(runs) == 1
    return json.loads(runs[0].read_text(encoding="utf-8"))


def test_full_run_from_silver_builds_every_layer_and_links_each_run_id(built_pipeline):
    context, results = built_pipeline["context"], built_pipeline["results"]
    record = read_record(context)

    assert record["estado"] == "completada" and record["error"] is None
    assert [(stage["etapa"], stage["resultado"]) for stage in record["etapas"]] == [(step, "correcta") for step in ALL_STEPS_FROM_SILVER]
    assert record["run_ids"]["plata_ine"] == results["plata_ine"]["run_id"]
    assert record["run_ids"]["modelo"] == results["modelo"]["run_id"]
    assert set(record["run_ids"]) == set(ALL_STEPS_FROM_SILVER) - {"integridad_bronce"}
    root = built_pipeline["root"]
    for relative in (
        "data/gold/indicadores/kpis_demograficos.parquet",
        "data/gold/indicadores/kpis_integrados_anual.parquet",
        "data/gold/modelo/fact_indicadores_anual.parquet",
        "data/gold/modelo/dm_panel_anual.parquet",
        "data/gold/escenarios/fact_proyecciones_demograficas.parquet",
        "data/serving/pensiones_espana.sqlite",
        "data/serving/postgresql/01_ddl.sql",
    ):
        assert (root / relative).is_file(), relative


def test_run_from_bronze_calls_the_three_extractors_before_continuing(tmp_path, monkeypatch):
    context = PipelineContext(tmp_path)
    calls = []

    def fake(name, publish, run_id):
        def extract(self, ids):
            calls.append(name)
            publish()
            return {"run_id": run_id, "manifest_path": str(tmp_path / f"{run_id}.manifest.json"), "records": list(ids)}

        return extract

    from fakes.fake_bronze import minimal_payloads

    monkeypatch.setattr(pipeline_module.IneExtractor, "__init__", lambda self, config: None)
    monkeypatch.setattr(pipeline_module.IneExtractor, "close", lambda self: None)
    monkeypatch.setattr(pipeline_module.IneExtractor, "extract_tables", fake("ine", lambda: context.bronze.run("ine_1", "2026-09-26T01:00:00.000000Z", minimal_payloads(sexes=("total", "hombres", "mujeres"))), "ine_1"))
    monkeypatch.setattr(pipeline_module.SeguridadSocialExtractor, "__init__", lambda self, config: None)
    monkeypatch.setattr(pipeline_module.SeguridadSocialExtractor, "close", lambda self: None)
    monkeypatch.setattr(pipeline_module.SeguridadSocialExtractor, "extract_files", fake("seguridad_social", lambda: context.social.run("seguridad_social_1", "2026-09-26T01:00:00.000000Z"), "seguridad_social_1"))
    monkeypatch.setattr(pipeline_module.EurostatExtractor, "__init__", lambda self, config: None)
    monkeypatch.setattr(pipeline_module.EurostatExtractor, "close", lambda self: None)
    monkeypatch.setattr(pipeline_module.EurostatExtractor, "extract_datasets", fake("eurostat", lambda: context.eurostat.run("eurostat_1", "2026-09-26T01:00:00.000000Z"), "eurostat_1"))

    results = run_pipeline(context, "bronce", "plata")

    assert calls == ["ine", "seguridad_social", "eurostat"]
    record = read_record(context)
    assert [stage["etapa"] for stage in record["etapas"]][:4] == ["bronce_ine", "bronce_seguridad_social", "bronce_eurostat", "integridad_bronce"]
    assert record["etapas_previstas"] == ["bronce", "plata"]
    assert results["plata_eurostat"]["bronze_run_ids"] == ["eurostat_1"]


def test_until_option_stops_after_the_requested_stage(tmp_path):
    context = PipelineContext(tmp_path)
    context.publish_bronze()

    run_pipeline(context, "plata", "indicadores")

    record = read_record(context)
    assert [stage["etapa"] for stage in record["etapas"]][-1] == "indicadores_integrados"
    assert not (tmp_path / "data" / "gold" / "modelo").exists()


def test_failure_writes_failed_record_and_raises(tmp_path):
    context = PipelineContext(tmp_path)

    with pytest.raises(ValueError, match="No hay manifiestos de Plata completados"):
        run_pipeline(context, "indicadores")

    record = read_record(context)
    assert record["estado"] == "fallida"
    assert "No hay manifiestos de Plata" in record["error"]
    assert [(stage["etapa"], stage["resultado"]) for stage in record["etapas"]] == [("indicadores_demografia", "fallida")]
    assert record["run_ids"] == {}


def test_silver_without_integrity_in_the_same_run_is_refused(tmp_path):
    context = PipelineContext(tmp_path)
    pipeline = Pipeline(context.config)
    try:
        with pytest.raises(RuntimeError, match="integridad"):
            pipeline._silver_ine()
    finally:
        reset_app_logger()


def test_tampered_bronze_stops_before_silver(tmp_path):
    context = PipelineContext(tmp_path)
    context.publish_bronze()
    payload = next(Path(context.config["sources"]["eurostat"]["storage"]["payloads_path"]).glob("pib_*.json"))
    payload.write_bytes(payload.read_bytes() + b" ")

    with pytest.raises(RuntimeError, match="integridad de Bronce eurostat"):
        run_pipeline(context, "plata")

    assert not (tmp_path / "data" / "silver" / "macro" / "stg_macro_anual.parquet").exists()


@pytest.mark.parametrize(("start", "end"), [("gold", None), ("modelo", "plata")])
def test_unknown_or_reversed_stages_are_rejected(tmp_path, start, end):
    context = PipelineContext(tmp_path)
    try:
        with pytest.raises(ValueError):
            Pipeline(context.config).run(start, end)
    finally:
        reset_app_logger()


def test_stage_order_is_the_medallion_order():
    assert STAGES == ("bronce", "plata", "indicadores", "modelo", "escenarios", "carga")


def test_output_directories_are_created_idempotently(tmp_path):
    context = PipelineContext(tmp_path)

    for _ in range(2):
        with pytest.raises(ValueError):
            run_pipeline(context, "indicadores")

    for folder in ("data/bronze", "data/silver", "data/gold", "logs", "logs/ejecuciones"):
        assert (tmp_path / folder).is_dir()
