import json

import pytest
import schedule

from src.programacion import ProgramadorETL


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def config(tmp_path, **ajustes):
    base = {"frecuencia": "cada_segundos", "dia": "lunes", "hora": "06:00", "intervalo": 1, "desde": "bronce", "hasta": "carga",
            "registro": str(tmp_path / "logs" / "programacion.jsonl")}
    return {"programacion": {**base, **ajustes}}


def registro(tmp_path):
    return [json.loads(line) for line in (tmp_path / "logs" / "programacion.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize(
    "ajustes, unidad, dia",
    [
        ({"frecuencia": "diaria"}, "days", None),
        ({"frecuencia": "semanal", "dia": "Miércoles"}, "weeks", "wednesday"),
        ({"frecuencia": "cada_minutos", "intervalo": 15}, "minutes", None),
        ({"frecuencia": "cada_segundos", "intervalo": 5}, "seconds", None),
    ],
)
def test_job_is_declared_from_the_configuration(tmp_path, ajustes, unidad, dia):
    programador = ProgramadorETL(config(tmp_path, **ajustes), ejecutar=lambda desde, hasta: None)

    trabajo = programador.programar()

    assert trabajo.unit == unidad
    assert trabajo.start_day == dia
    assert "pipeline_etl" in trabajo.tags
    assert programador.scheduler.jobs == [trabajo]


@pytest.mark.parametrize("ajustes", [{"frecuencia": "mensual"}, {"frecuencia": "semanal", "dia": "funday"}])
def test_invalid_frequency_or_day_is_rejected(tmp_path, ajustes):
    with pytest.raises(ValueError, match="no válid"):
        ProgramadorETL(config(tmp_path, **ajustes), ejecutar=lambda desde, hasta: None).programar()


def test_scheduled_runs_execute_the_pipeline_and_are_logged(tmp_path, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(schedule.datetime, "datetime", _FrozenDatetime.bound_to(clock))
    llamadas = []
    programador = ProgramadorETL(config(tmp_path, desde="plata", hasta="modelo"), ejecutar=lambda desde, hasta: llamadas.append((desde, hasta)) or {"run_id": f"run_{len(llamadas)}"})
    programador.programar()

    ejecuciones = programador.iniciar(max_ejecuciones=2, espera_s=1, reloj=clock, dormir=clock.sleep)

    assert llamadas == [("plata", "modelo"), ("plata", "modelo")]
    assert [entrada["run_id"] for entrada in ejecuciones] == ["run_1", "run_2"]
    assert [entrada["estado"] for entrada in registro(tmp_path)] == ["completada", "completada"]


def test_a_failing_run_is_logged_and_does_not_stop_the_scheduler(tmp_path):
    def falla(desde, hasta):
        raise ConnectionError("INE no responde")

    programador = ProgramadorETL(config(tmp_path), ejecutar=falla)

    entrada = programador.ejecutar_trabajo()

    assert entrada["estado"] == "fallida"
    assert entrada["error"] == "ConnectionError: INE no responde"
    assert registro(tmp_path)[0]["run_id"] is None


def test_loop_stops_at_the_time_limit_when_nothing_is_due(tmp_path):
    clock = FakeClock()
    programador = ProgramadorETL(config(tmp_path, frecuencia="semanal"), ejecutar=lambda desde, hasta: None)
    programador.programar()

    assert programador.iniciar(espera_s=10, limite_s=30, reloj=clock, dormir=clock.sleep) == []
    assert clock.now == 30
    programador.detener()
    assert programador.scheduler.jobs == []


class _FrozenDatetime:
    """Sustituye `datetime.datetime` dentro de schedule para que el reloj falso controle cuándo vence el trabajo."""

    @staticmethod
    def bound_to(clock):
        import datetime as real

        origin = real.datetime(2026, 1, 5, 6, 0, 0)

        class Frozen(real.datetime):
            @classmethod
            def now(cls, tz=None):
                return origin + real.timedelta(seconds=clock.now)

        return Frozen
