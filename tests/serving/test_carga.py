from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from src.serving.carga import Carga
from src.serving.esquema_relacional import TABLES, VIEWS, load_order
from fakes.pipeline_context import PipelineContext, reset_app_logger
from src.pipeline import Pipeline


def sqlite_path(built_pipeline):
    return Path(built_pipeline["root"]) / "data" / "serving" / "pensiones_espana.sqlite"


def test_every_table_is_loaded_with_the_same_rows_as_its_parquet(built_pipeline):
    rows = built_pipeline["results"]["carga"]["rows"]
    model_rows = built_pipeline["results"]["modelo"]["rows"]
    scenario_rows = built_pipeline["results"]["escenarios"]["rows"]

    assert set(rows) == set(TABLES)
    for name, count in {**model_rows, **scenario_rows}.items():
        assert rows[name] == count


def test_primary_and_foreign_keys_are_enforced_by_the_database(built_pipeline):
    connection = sqlite3.connect(sqlite_path(built_pipeline))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        foreign = connection.execute("PRAGMA foreign_key_list(fact_indicadores_anual)").fetchall()
        assert {row[2] for row in foreign} == {"dim_tiempo", "dim_territorio", "dim_sexo", "dim_grupo_edad", "dim_indicador", "dim_fuente"}
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO fact_indicadores_anual (tiempo_key, territorio_key, sexo_key, grupo_edad_key, indicador_key, fuente_key, valor) VALUES (1800, 1, 0, 0, 1, 1, 1.0)")
        first = connection.execute("SELECT tiempo_key, territorio_key, sexo_key, grupo_edad_key, indicador_key FROM fact_indicadores_anual LIMIT 1").fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO fact_indicadores_anual (tiempo_key, territorio_key, sexo_key, grupo_edad_key, indicador_key, fuente_key, valor) VALUES (?, ?, ?, ?, ?, 1, 1.0)", first)
    finally:
        connection.close()


def test_views_return_denormalized_rows_for_power_bi(built_pipeline):
    connection = sqlite3.connect(sqlite_path(built_pipeline))
    try:
        for name in VIEWS:
            assert connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] > 0
        kpis = {row[0] for row in connection.execute("SELECT DISTINCT codigo_kpi FROM vw_kpis_observados")}
        assert kpis == {f"KPI-0{number}" for number in range(1, 9)}
    finally:
        connection.close()


def test_csv_and_postgresql_scripts_are_generated(built_pipeline):
    root = Path(built_pipeline["root"]) / "data" / "serving"
    for name in TABLES:
        assert len(pd.read_csv(root / "csv" / f"{name}.csv", encoding="utf-8-sig")) == built_pipeline["results"]["carga"]["rows"][name]
    ddl = (root / "postgresql" / "01_ddl.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE pensiones.fact_indicadores_anual" in ddl
    assert "FOREIGN KEY (indicador_key) REFERENCES pensiones.dim_indicador (indicador_key)" in ddl
    assert "CREATE VIEW pensiones.vw_kpis_observados" in ddl
    load = (root / "postgresql" / "02_carga.sql").read_text(encoding="utf-8")
    assert load.count("\\copy") == len(TABLES)


def test_dimensions_are_loaded_before_facts():
    order = load_order()
    for name, spec in TABLES.items():
        for target in spec["fk"].values():
            assert order.index(target) < order.index(name)


def test_quality_rules_of_every_layer_are_consolidated(built_pipeline):
    connection = sqlite3.connect(sqlite_path(built_pipeline))
    try:
        layers = {row[0] for row in connection.execute("SELECT DISTINCT capa FROM aux_calidad_reglas")}
        failures = connection.execute("SELECT COUNT(*) FROM aux_calidad_reglas WHERE resultado = 'falla'").fetchone()[0]
    finally:
        connection.close()
    assert layers == {"plata_ine", "plata_seguridad_social", "plata_eurostat", "indicadores_demografia", "indicadores_pensiones", "indicadores_integrados", "modelo", "escenarios"}
    assert failures == 0


def test_tampered_gold_parquet_is_not_loaded(tmp_path):
    context = PipelineContext(tmp_path)
    context.publish_bronze()
    try:
        Pipeline(context.config).run("plata", "escenarios")
    finally:
        reset_app_logger()
    fact = tmp_path / "data" / "gold" / "modelo" / "fact_indicadores_anual.parquet"
    fact.write_bytes(fact.read_bytes() + b"x")

    try:
        with pytest.raises(ValueError, match="no coincide con el manifiesto"):
            Carga(context.config).run()
    finally:
        reset_app_logger()
    assert not (tmp_path / "data" / "serving" / "pensiones_espana.sqlite").exists()


def test_reload_succeeds_while_another_program_holds_the_database_open(built_pipeline):
    """En Windows, os.replace sobre una base abierta fallaba con WinError 5 (Acceso denegado)."""
    reader = sqlite3.connect(sqlite_path(built_pipeline))
    try:
        assert reader.execute("SELECT COUNT(*) FROM dim_tiempo").fetchone()[0] > 0
        try:
            result = Carga(built_pipeline["config"]).run()
        finally:
            reset_app_logger()
        assert result["rows"]["fact_indicadores_anual"] == reader.execute("SELECT COUNT(*) FROM fact_indicadores_anual").fetchone()[0]
    finally:
        reader.close()
    assert not sqlite_path(built_pipeline).with_suffix(".sqlite.tmp").exists()


def test_persistently_locked_file_fails_with_an_actionable_message(built_pipeline, monkeypatch, tmp_path):
    import src.serving.carga as carga_module

    def locked(source, target):
        raise PermissionError(5, "Acceso denegado")

    monkeypatch.setattr(carga_module.os, "replace", locked)
    monkeypatch.setattr(carga_module.time, "sleep", lambda seconds: None)
    temporary = tmp_path / "x.csv.tmp"
    temporary.write_text("a", encoding="utf-8")
    carga = Carga(built_pipeline["config"])
    try:
        with pytest.raises(PermissionError, match="abierto en otro programa"):
            carga._replace(temporary, tmp_path / "x.csv")
    finally:
        reset_app_logger()
    assert not temporary.exists()
