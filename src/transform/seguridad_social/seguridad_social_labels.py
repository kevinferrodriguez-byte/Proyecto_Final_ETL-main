import math
import numbers

import pandas as pd

MESES = {
    "enero": 1, "ene": 1,
    "febrero": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6,
    "julio": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "septiembre": 9, "sep": 9, "set": 9,
    "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12,
}


def normalize_label(value):
    return " ".join(str(value).split()).upper()


def is_empty(value):
    if value is None or value is pd.NA:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def month_number(label):
    return MESES.get(str(label).strip().lower())


def count_value(value, description):
    if is_empty(value):
        return pd.NA
    if isinstance(value, bool) or not isinstance(value, numbers.Number):
        raise ValueError(f"{description} tiene un valor no numérico: {value!r}.")
    if value != int(value):
        raise ValueError(f"{description} tiene un recuento no entero: {value!r}.")
    return int(value)


def amount_value(value, description):
    if is_empty(value):
        return pd.NA
    if isinstance(value, bool) or not isinstance(value, numbers.Number):
        raise ValueError(f"{description} tiene un importe no numérico: {value!r}.")
    return float(value)


def find_header(grid, label, search_rows, description):
    wanted = normalize_label(label)
    matches = [
        (row, column)
        for row in range(min(search_rows, len(grid)))
        for column in range(grid.shape[1])
        if not is_empty(grid.iat[row, column]) and normalize_label(grid.iat[row, column]) == wanted
    ]
    if not matches:
        raise ValueError(f"{description} no tiene el encabezado '{label}' en sus primeras {search_rows} filas; el formato no es el esperado.")
    if len(matches) > 1:
        raise ValueError(f"{description} repite el encabezado '{label}' en las celdas {matches}; el formato no es el esperado.")
    return matches[0]
