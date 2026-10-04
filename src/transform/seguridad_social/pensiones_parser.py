from datetime import date
import numbers

import pandas as pd

from src.transform.seguridad_social.seguridad_social_labels import amount_value, count_value, find_header, is_empty, month_number, normalize_label

HEADER_SEARCH_ROWS = 10
VALUE_READERS = {"count": count_value, "amount": amount_value}
PERIOD_COLUMNS = ["periodo_original", "tipo_corte", "fecha_referencia", "anyo", "mes"]


class PensionesParser:
    def __init__(self, config):
        self.period_header = config["period_header"]
        self.end_marker = normalize_label(config["end_marker"])
        self.columns = config["columns"]
        self.annual_month = config["annual_reference"]["month"]
        self.annual_note = config["annual_reference"]["source_note"]
        value_type = config.get("value_type", "count")
        if value_type not in VALUE_READERS:
            raise ValueError(f"value_type '{value_type}' no soportado; use uno de: {', '.join(VALUE_READERS)}.")
        self.read_value = VALUE_READERS[value_type]

    def parse(self, grid):
        description = "La hoja de pensiones"
        header_row, year_column = find_header(grid, self.period_header, HEADER_SEARCH_ROWS, description)
        month_column = year_column + 1
        value_columns = self._value_columns(grid, header_row, year_column, description)
        self._require_annual_note(grid, description)
        records = []
        unpublished = []
        year = None
        for position in range(header_row + 1, len(grid)):
            if self._is_end(grid, position):
                break
            year_cell = grid.iat[position, year_column]
            month_cell = grid.iat[position, month_column]
            raw = {name: grid.iat[position, column] for name, column in value_columns.items()}
            if is_empty(year_cell) and is_empty(month_cell) and all(is_empty(value) for value in raw.values()):
                continue
            if not is_empty(year_cell):
                year = self._year(year_cell, position, description)
            if year is None:
                raise ValueError(f"{description} tiene un mes sin año en la fila {position + 1}.")
            period = self._period(year, month_cell, position, description)
            if all(is_empty(value) for value in raw.values()):
                if period["tipo_corte"] == "anual":
                    raise ValueError(f"{description} tiene el año {year} sin valores en la fila {position + 1}.")
                unpublished.append(period["periodo_original"])
                continue
            counts = {name: self.read_value(value, f"{description} en {period['periodo_original']} ({name})") for name, value in raw.items()}
            records.append({**period, **counts})
        if not records:
            raise ValueError(f"{description} no contiene filas de periodo bajo '{self.period_header}'; el formato no es el esperado.")
        return {"frame": pd.DataFrame(records, columns=PERIOD_COLUMNS + list(value_columns)), "unpublished": unpublished}

    def _value_columns(self, grid, header_row, year_column, description):
        expected = {normalize_label(label): name for label, name in self.columns.items()}
        found = {}
        unexpected = []
        for column in range(grid.shape[1]):
            cell = grid.iat[header_row, column]
            if column == year_column or is_empty(cell):
                continue
            label = normalize_label(cell)
            if label in expected:
                found[expected[label]] = column
            else:
                unexpected.append(str(cell).strip())
        missing = [label for label, name in self.columns.items() if name not in found]
        if missing:
            raise ValueError(f"{description} no tiene las columnas esperadas: {', '.join(missing)}; el formato no es el esperado.")
        if unexpected:
            raise ValueError(f"{description} tiene columnas no previstas: {', '.join(unexpected)}; revise silver.seguridad_social.pensiones.columns.")
        return {name: found[name] for name in self.columns.values()}

    def _require_annual_note(self, grid, description):
        wanted = normalize_label(self.annual_note)
        for value in grid.to_numpy().ravel():
            if not is_empty(value) and normalize_label(value) == wanted:
                return
        raise ValueError(
            f"{description} no incluye la nota '{self.annual_note}'; sin ella no se puede asignar el mes "
            f"{self.annual_month} a las filas anuales y no se promueve a Plata."
        )

    def _is_end(self, grid, position):
        return any(not is_empty(value) and normalize_label(value).startswith(self.end_marker) for value in grid.iloc[position])

    def _year(self, value, position, description):
        if isinstance(value, numbers.Number) and not isinstance(value, bool) and value == int(value):
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        raise ValueError(f"{description} tiene un año no válido {value!r} en la fila {position + 1}.")

    def _period(self, year, month_cell, position, description):
        if is_empty(month_cell):
            return {"periodo_original": str(year), "tipo_corte": "anual", "fecha_referencia": date(year, self.annual_month, 1), "anyo": year, "mes": self.annual_month}
        month = month_number(month_cell)
        if month is None:
            raise ValueError(f"{description} tiene un mes desconocido {month_cell!r} en la fila {position + 1}.")
        return {"periodo_original": f"{year} {str(month_cell).strip()}", "tipo_corte": "mensual", "fecha_referencia": date(year, month, 1), "anyo": year, "mes": month}
