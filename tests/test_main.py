import sys

import pytest

from main import main
from fakes.pipeline_context import PipelineContext, reset_app_logger


def run_main(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["main.py"] + arguments)
    try:
        return main()
    finally:
        reset_app_logger()


def test_main_returns_zero_when_every_stage_succeeds(tmp_path, monkeypatch):
    context = PipelineContext(tmp_path)
    context.publish_bronze()

    assert run_main(monkeypatch, ["--desde", "plata", "--hasta", "indicadores", "--config", str(context.write_config())]) == 0
    assert (tmp_path / "data" / "gold" / "indicadores" / "kpis_integrados_anual.parquet").exists()


def test_main_returns_non_zero_when_a_stage_fails(tmp_path, monkeypatch, capsys):
    context = PipelineContext(tmp_path)

    assert run_main(monkeypatch, ["--desde", "modelo", "--config", str(context.write_config())]) == 1
    assert "El pipeline terminó con errores" in capsys.readouterr().err


def test_main_returns_non_zero_when_configuration_is_missing(tmp_path, monkeypatch):
    assert run_main(monkeypatch, ["--config", str(tmp_path / "no_existe.yaml")]) == 1


def test_main_rejects_unknown_stage_with_usage_error(monkeypatch):
    with pytest.raises(SystemExit) as exit_info:
        run_main(monkeypatch, ["--desde", "gold"])

    assert exit_info.value.code == 2
