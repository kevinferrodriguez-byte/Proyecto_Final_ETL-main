from datetime import date

import pytest

from src.transform.age_partition import AgePartition
from fakes.demografia_rows import all_ages, frame_from, open_interval, simple_age

TOP_AGE = 3


def period(year):
    return {"fecha_referencia": date(year, 1, 1), "anyo": year}


def semi(age, valor, year):
    row = period(year)
    row.update({"consulta": "semiintervalos_edad", "es_control": True})
    return open_interval(age, valor, row)


def early_period():
    year = 1975
    return [simple_age(0, 10.0, period(year)), simple_age(1, 9.0, period(year)), semi(2, 8.0, year), all_ages(27.0, period(year))]


def middle_period():
    year = 1990
    return [
        simple_age(0, 10.0, period(year)),
        simple_age(1, 9.0, period(year)),
        simple_age(2, 8.0, period(year)),
        semi(2, 15.0, year),
        semi(3, 7.0, year),
        all_ages(34.0, period(year)),
    ]


def null_ages_period():
    year = 2005
    return [
        simple_age(0, 10.0, period(year)),
        simple_age(1, 9.0, period(year)),
        simple_age(2, 8.0, period(year)),
        simple_age(3, None, period(year)),
        simple_age(4, None, period(year)),
        semi(2, 15.0, year),
        semi(3, 7.0, year),
        all_ages(34.0, period(year)),
    ]


def recent_period():
    year = 2020
    return [
        simple_age(0, 10.0, period(year)),
        simple_age(1, 9.0, period(year)),
        simple_age(2, 8.0, period(year)),
        simple_age(3, 4.0, period(year)),
        simple_age(4, 2.0, period(year)),
        open_interval(5, 1.0, period(year)),
        semi(2, 15.0, year),
        semi(3, 7.0, year),
        all_ages(34.0, period(year)),
    ]


def detail_ages(frame, year):
    rows = frame[frame["anyo"].eq(year) & ~frame["es_control"]]
    return sorted(zip(rows["tipo_edad"], rows["edad_min"]))


def control_ages(frame, year):
    rows = frame[frame["anyo"].eq(year) & frame["es_control"]]
    return sorted(zip(rows["tipo_edad"], rows["edad_min"]))


def test_current_open_interval_completes_each_period():
    frame = frame_from(early_period() + middle_period())

    result = AgePartition(TOP_AGE).apply(frame)["frame"]

    assert detail_ages(result, 1975) == [("simple", 0), ("simple", 1), ("tramo_abierto", 2)]
    assert control_ages(result, 1975) == [("total", 0)]
    assert detail_ages(result, 1990) == [("simple", 0), ("simple", 1), ("simple", 2), ("tramo_abierto", 3)]
    assert control_ages(result, 1990) == [("total", 0), ("tramo_abierto", 2)]


def test_simple_ages_without_value_are_discarded():
    frame = frame_from(null_ages_period())

    result = AgePartition(TOP_AGE).apply(frame)["frame"]

    assert len(result) == len(frame) - 2
    assert result["valor"].notna().all()
    assert detail_ages(result, 2005) == [("simple", 0), ("simple", 1), ("simple", 2), ("tramo_abierto", 3)]


def test_later_open_interval_is_homologated_to_published_top_interval():
    frame = frame_from(recent_period())

    partitioned = AgePartition(TOP_AGE).apply(frame)
    result = partitioned["frame"]

    assert detail_ages(result, 2020) == [("simple", 0), ("simple", 1), ("simple", 2), ("tramo_abierto", 3)]
    assert control_ages(result, 2020) == [("simple", 3), ("simple", 4), ("total", 0), ("tramo_abierto", 2), ("tramo_abierto", 5)]
    homologated = result[result["anyo"].eq(2020) & result["tipo_edad"].eq("tramo_abierto") & result["edad_min"].eq(3)]
    assert homologated["consulta"].tolist() == ["semiintervalos_edad"]
    assert partitioned["homologation"][["published", "components"]].values.tolist() == [[7.0, 7.0]]


def test_periods_without_homologation_have_no_homologation_check():
    homologation = AgePartition(TOP_AGE).apply(frame_from(early_period() + middle_period()))["homologation"]

    assert homologation.empty


def test_tables_without_age_breakdown_are_left_untouched():
    rows = [{"tabla_id": "6566", "metrica": "nacimientos", "tipo_edad": "total", "edad_max": None, "edad_etiqueta_original": "Todas las edades"}]
    frame = frame_from(rows + early_period())

    result = AgePartition(TOP_AGE).apply(frame)["frame"]

    untouched = result[result["tabla_id"].eq("6566")]
    assert len(untouched) == 1 and not untouched["es_control"].iloc[0]


def test_missing_current_open_interval_is_rejected():
    rows = [row for row in early_period() if row["tipo_edad"] != "tramo_abierto"]

    with pytest.raises(ValueError, match="falla en 1 grupos: sin exactamente un tramo abierto vigente"):
        AgePartition(TOP_AGE).apply(frame_from(rows))


def test_non_contiguous_simple_ages_are_rejected():
    rows = [row for row in middle_period() if not (row["tipo_edad"] == "simple" and row["edad_min"] == 1)]

    with pytest.raises(ValueError, match="falla en 1 grupos: sin edades simples contiguas desde 0"):
        AgePartition(TOP_AGE).apply(frame_from(rows))


def test_missing_published_homologated_interval_is_rejected():
    rows = [row for row in recent_period() if not (row["tipo_edad"] == "tramo_abierto" and row["edad_min"] == 3)]

    with pytest.raises(ValueError, match="falla en 1 grupos: sin exactamente un tramo abierto homologado"):
        AgePartition(TOP_AGE).apply(frame_from(rows))
