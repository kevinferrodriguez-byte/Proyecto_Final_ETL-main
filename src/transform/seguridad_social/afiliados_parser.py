from datetime import date
import calendar
import re

import pandas as pd

from src.transform.seguridad_social.seguridad_social_labels import count_value, find_header, is_empty, month_number

HEADER_SEARCH_ROWS = 10
PERIOD_PATTERN = re.compile(r"^([^\W\d_]+)\s+(\d{4})$")
COLUMNS = ["periodo_original", "fecha_referencia", "anyo", "mes", "total_afiliados"]


class AfiliadosParser:
    def __init__(self, config):
        self.period_header = config["period_header"]
        self.total_header = config["total_header"]

    def parse(self, grid):
        description = "La hoja de afiliados"
        period_row, period_column = find_header(grid, self.period_header, HEADER_SEARCH_ROWS, description)
        total_row, total_column = find_header(grid, self.total_header, HEADER_SEARCH_ROWS, description)
        records = []
        for position in range(max(period_row, total_row) + 1, len(grid)):
            label = grid.iat[position, period_column]
            if is_empty(label):
                continue
            text = " ".join(str(label).split())
            match = PERIOD_PATTERN.match(text)
            if match is None:
                continue
            month = month_number(match[1])
            if month is None:
                raise ValueError(f"{description} tiene un mes desconocido en '{text}' (fila {position + 1}).")
            year = int(match[2])
            records.append(
                {
                    "periodo_original": text,
                    "fecha_referencia": date(year, month, calendar.monthrange(year, month)[1]),
                    "anyo": year,
                    "mes": month,
                    "total_afiliados": count_value(grid.iat[position, total_column], f"{description} en '{text}'"),
                }
            )
        if not records:
            raise ValueError(f"{description} no contiene filas con periodo 'Mes Año' bajo '{self.period_header}'; el formato no es el esperado.")
        return pd.DataFrame(records, columns=COLUMNS)
