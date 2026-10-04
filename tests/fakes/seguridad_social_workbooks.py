from io import BytesIO

import pandas as pd
from openpyxl import Workbook

MONTH_NAMES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
MONTH_ABBREVIATIONS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
PENSION_HEADER = ["PERIODO", None, "INCAPACIDAD  PERMANENTE", "JUBILACIÓN", "VIUDEDAD", "ORFANDAD", "F. FAMILIAR", "TOTAL"]
ANNUAL_NOTE = "Datos anuales a diciembre de cada año."
TOTAL_COLUMN = 4


def months(start, end):
    return [(period.year, period.month) for period in pd.period_range(start, end, freq="M")]


def afiliados_total(year, month):
    return 17_000_000 + (year - 2016) * 400_000 + month * 1_000


def afiliados_rows(periods=None, values=None, total_header="TOTAL SISTEMA"):
    periods = months("2016-01", "2026-08") if periods is None else periods
    values = values or {}
    rows = [
        ["Datos totales de afiliados en alta por Regímenes (Último Día del mes)"],
        ["Régimen", "REGIMEN GENERAL\n", None, "RÉGIMEN ESPECIAL DE AUTÓNOMOS", total_header],
        ["Periodo", "Régimen General (1) \n", "Sistema Especial Agrario (2)", "Régimen Especial de Trabajadores Autónomos (4)", None],
    ]
    for year, month in periods:
        label = values.get(("label", year, month), f"{MONTH_NAMES[month - 1]} {year}")
        total = values.get((year, month), afiliados_total(year, month))
        rows.append([label, 12_000_000, 700_000, 3_000_000, total])
    rows.append(["(1) No incluye los Sistemas Especiales Agrario y de Empleados de Hogar vigentes desde 1-enero-2012."])
    rows.append([None])
    return rows


def pension_classes(total):
    classes = [total // 10, total * 6 // 10, total * 2 // 10, total // 30]
    return classes + [total - sum(classes)]


def pension_total(year, month=12):
    return 9_400_000 + (year - 2016) * 100_000 + month * 1_000


def pension_row(year_cell, month_cell, total):
    return [year_cell, month_cell] + pension_classes(total) + [total]


def pensiones_rows(annual_years=range(2016, 2026), monthly=None, unpublished=None, note=ANNUAL_NOTE, header=None, overrides=None):
    monthly = months("2025-01", "2026-09") if monthly is None else monthly
    unpublished = months("2026-10", "2026-12") if unpublished is None else unpublished
    overrides = overrides or {}
    rows = [
        [None, None, "NÚMERO DE PENSIONES POR CLASE DE PENSIÓN"],
        [None, None, "Pensiones en vigor a día 1 de cada mes"],
        [None],
        list(header or PENSION_HEADER),
        [None],
    ]
    for year in annual_years:
        rows.append(overrides.get(("anual", year), pension_row(year, None, pension_total(year))))
    rows.append([None])
    previous_year = None
    for year, month in list(monthly) + list(unpublished):
        year_cell = year if year != previous_year else None
        previous_year = year
        if (year, month) in unpublished:
            rows.append([year_cell, MONTH_ABBREVIATIONS[month - 1], "", "", "", "", "", ""])
        else:
            rows.append(overrides.get(("mensual", year, month), pension_row(year_cell, MONTH_ABBREVIATIONS[month - 1], pension_total(year, month))))
    rows += [[None], [None, None, "% de variación anual"], [2016, None, 0.84, 1.72, 0.23, 0.08, 2.33, 1.20], [None]]
    if note:
        rows.append([note])
    return rows


def grid(rows):
    width = max(len(row) for row in rows)
    return pd.DataFrame([list(row) + [None] * (width - len(row)) for row in rows], dtype=object)


def workbook_bytes(sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(list(row))
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def afiliados_workbook(**options):
    return workbook_bytes({"Hoja1": afiliados_rows(**options)})


def importe_rows(**options):
    rows = pensiones_rows(**options)
    amounts = []
    in_values = True
    for row in rows:
        if any(isinstance(cell, str) and cell.strip().startswith("% de variación") for cell in row):
            in_values = False
        if in_values and len(row) == 8 and isinstance(row[7], int):
            amounts.append(row[:2] + [value * 0.9 + 0.123 for value in row[2:7]] + [sum(value * 0.9 + 0.123 for value in row[2:7])])
        else:
            amounts.append(row)
    return amounts


def pensiones_workbook(**options):
    return workbook_bytes(
        {
            "Portada": [["EVOLUCIÓN MENSUAL DE LAS PENSIONES"]],
            "Nº Pens. Clases": pensiones_rows(**options),
            "Importe €": importe_rows(**options),
        }
    )
