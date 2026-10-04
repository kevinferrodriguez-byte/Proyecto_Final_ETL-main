from datetime import date, datetime, timezone

import pandas as pd

from src.indicators.integrados import IndicadoresIntegrados
from src.quality.integrados_quality import IntegradosQuality
from src.quality.quality_evaluation import QualityEvaluation
from fakes.pipeline_context import PipelineContext

GENERATED = datetime(2026, 9, 29, tzinfo=timezone.utc)


def macro_frame(rows):
    frame = pd.DataFrame(rows, columns=["anyo", "metrica", "valor", "estado_dato"])
    return frame.assign(territorio="ES")


def test_pension_spending_ratio_keeps_numerator_denominator_and_published_value(tmp_path):
    config = PipelineContext(tmp_path).config
    macro = macro_frame(
        [
            (2023, "gasto_pensiones", 197055.65, "observado"),
            (2023, "pib", 1497761.0, "provisional"),
            (2023, "gasto_pensiones_pib_publicado", 13.16, "observado"),
            (2024, "gasto_pensiones", 210875.25, "observado"),
        ]
    )

    frame = IndicadoresIntegrados(config).pension_spending(macro, "silver_eurostat_1")

    assert frame["anyo"].tolist() == [2023]
    row = frame.iloc[0]
    assert round(row["valor"], 4) == round(197055.65 / 1497761.0 * 100, 4)
    assert row["numerador"] == 197055.65 and row["denominador"] == 1497761.0
    assert row["estado_dato"] == "provisional"
    assert abs(row["diferencia_publicado"]) < 0.005


def test_affiliation_rate_pairs_december_with_population_of_next_1_january(tmp_path):
    config = PipelineContext(tmp_path).config
    afiliados = pd.DataFrame({"anyo": [2019, 2019], "mes": [11, 12], "territorio": "ES", "fecha_referencia": [date(2019, 11, 30), date(2019, 12, 31)], "total_afiliados": [90, 100]})
    ages = [(0, 0, 10.0), (1, 1, 30.0), (2, 2, 20.0), (3, None, 5.0)]
    population = pd.DataFrame(
        [
            {"anyo": 2020, "fecha_referencia": date(2020, 1, 1), "territorio": "ES", "fuente": "INE", "estado_dato": "observado", "escenario": "observado", "sexo": "total", "metrica": "poblacion", "es_control": False, "edad_min": low, "edad_max": high, "valor": value}
            for low, high, value in ages
        ]
    ).astype({"edad_max": "Int64"})

    frame = IndicadoresIntegrados(config).affiliation_rate(afiliados, "silver_ss_1", population, "silver_ine_1")

    assert frame[["anyo", "valor", "numerador", "denominador"]].values.tolist() == [[2019, 200.0, 100.0, 50.0]]
    assert frame["fecha_referencia_denominador"].iloc[0] == date(2020, 1, 1)


def test_quality_rejects_incoherent_values_and_only_warns_on_published_difference(built_pipeline):
    config = built_pipeline["config"]
    frame = pd.read_parquet(built_pipeline["results"]["indicadores_integrados"]["path"])
    quality = IntegradosQuality(config)

    shifted = frame.copy()
    shifted.loc[shifted["indicador"].eq("gasto_pensiones_pib"), "diferencia_publicado"] = 0.5
    warned = quality.evaluate(shifted, QualityEvaluation())
    assert warned.passed()
    assert [rule["regla"] for rule in warned.rules if rule["resultado"] == "advertencia"] == ["consistencia_publicado"]

    broken = frame.copy()
    broken.loc[0, "valor"] += 1.0
    rejected = quality.evaluate(broken, QualityEvaluation())
    assert [rule["regla"] for rule in rejected.rules if rule["resultado"] == "falla"] == ["coherencia_calculo"]
