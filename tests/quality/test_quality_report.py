import json
import logging

from src.quality.quality_evaluation import QualityEvaluation
from src.quality.quality_report import QualityReport


def evaluation_with(*results):
    evaluation = QualityEvaluation()
    for index, result in enumerate(results):
        name = f"regla_{index}"
        if result == "cumple":
            evaluation.check(name, "descripción", [])
        elif result == "falla":
            evaluation.check(name, "descripción", ["problema"])
        elif result == "advertencia":
            evaluation.warn(name, "descripción", ["hallazgo"])
        else:
            evaluation.skip(name, "descripción", "motivo")
    return evaluation


def write(tmp_path, caplog, evaluation, cause=None):
    caplog.set_level(logging.INFO, logger="src")
    path = QualityReport(tmp_path, "Oro sostenibilidad").write("run_1", evaluation, cause)
    messages = [record.getMessage() for record in caplog.records if "Calidad de" in record.getMessage()]
    return json.loads(open(path, encoding="utf-8").read()), messages


def test_summary_counts_each_result_separately():
    evaluation = evaluation_with("cumple", "cumple", "advertencia", "falla", "no_evaluada")

    assert evaluation.summary() == {"aprobadas": 2, "advertencias": 1, "fallas": 1, "no_evaluadas": 1}


def test_warning_does_not_change_passed_semantics():
    assert evaluation_with("cumple", "advertencia").passed()
    assert not evaluation_with("cumple", "falla").passed()


def test_warning_without_findings_counts_as_approved():
    evaluation = QualityEvaluation()
    evaluation.warn("atipicos", "descripción", [])

    assert evaluation.summary()["aprobadas"] == 1


def test_approved_report_with_warning_shows_approved_warnings_and_failures(tmp_path, caplog):
    report, messages = write(tmp_path, caplog, evaluation_with(*["cumple"] * 24, "advertencia"))

    assert report["estado"] == "aprobado"
    assert report["resumen"] == {"aprobadas": 24, "advertencias": 1, "fallas": 0, "no_evaluadas": 0}
    assert messages == ["Calidad de Oro sostenibilidad aprobada: 24 reglas aprobadas · 1 advertencia · 0 fallas"]


def test_fully_approved_report_keeps_the_existing_message(tmp_path, caplog):
    report, messages = write(tmp_path, caplog, evaluation_with("cumple", "cumple"))

    assert report["resumen"]["aprobadas"] == 2
    assert messages == ["Calidad de Oro sostenibilidad aprobada: 2 de 2 reglas cumplen"]


def test_rejected_report_shows_the_breakdown(tmp_path, caplog):
    report, messages = write(tmp_path, caplog, evaluation_with("cumple", "falla", "no_evaluada"), cause="motivo del rechazo")

    assert report["estado"] == "rechazado"
    assert messages[0].startswith("Calidad de Oro sostenibilidad rechazada (1 regla aprobada · 0 advertencias · 1 falla · 1 no evaluada)")
