import pytest

from src.transform.eurostat.jsonstat_parser import JsonStatParser
from fakes.fake_eurostat import jsonstat


def test_sparse_values_are_decoded_in_row_major_order_with_flags():
    payload = jsonstat([("unit", ["A", "B"]), ("time", ["2020", "2021", "2022"])], {0: 1.0, 2: 3.0, 4: 5.0}, {4: "p"})

    frame = JsonStatParser().parse(payload)

    assert frame[["unit", "time", "valor"]].values.tolist() == [["A", "2020", 1.0], ["A", "2022", 3.0], ["B", "2021", 5.0]]
    assert frame["flag"].isna().tolist() == [True, True, False]
    assert frame["flag"].iloc[2] == "p"


def test_missing_positions_do_not_create_rows():
    payload = jsonstat([("time", ["2020", "2021"])], {1: 7.0})

    assert JsonStatParser().parse(payload)["time"].tolist() == ["2021"]


def test_inconsistent_dimension_size_is_rejected():
    payload = jsonstat([("time", ["2020", "2021"])], {0: 1.0})
    payload["size"] = [3]

    with pytest.raises(ValueError, match="tamaño 3"):
        JsonStatParser().parse(payload)
