from datetime import date

from fakes.demografia_rows import frame_from

KNOWN_AGES = [(0, 0, 10.0), (15, 15, 5.0), (16, 16, 40.0), (64, 64, 20.0), (65, 65, 12.0), (100, None, 3.0)]


def population(year, escenario="observado", ages=None, sexo="total"):
    estado = "observado" if escenario == "observado" else "proyectado"
    table_id = "56934" if escenario == "observado" else "36643"
    rows = []
    for edad_min, edad_max, valor in ages or KNOWN_AGES:
        rows.append(
            {
                "tabla_id": table_id,
                "fecha_referencia": date(year, 1, 1),
                "anyo": year,
                "sexo": sexo,
                "edad_min": edad_min,
                "edad_max": edad_max,
                "tipo_edad": "simple" if edad_max is not None else "tramo_abierto",
                "edad_etiqueta_original": f"{edad_min} años" if edad_max is not None else f"{edad_min} y más años",
                "valor": valor,
                "estado_dato": estado,
                "escenario": escenario,
            }
        )
    total = sum(valor for edad_min, edad_max, valor in ages or KNOWN_AGES)
    rows.append(
        {
            "tabla_id": table_id,
            "consulta": "total_edad",
            "fecha_referencia": date(year, 1, 1),
            "anyo": year,
            "sexo": sexo,
            "edad_min": 0,
            "edad_max": None,
            "tipo_edad": "total",
            "edad_etiqueta_original": "Todas las edades",
            "valor": total,
            "estado_dato": estado,
            "escenario": escenario,
            "es_control": True,
        }
    )
    return rows


def vital(year, births, deaths):
    common = {
        "tabla_id": "6566",
        "fecha_referencia": date(year, 1, 1),
        "anyo": year,
        "tipo_edad": "total",
        "edad_min": 0,
        "edad_max": None,
        "edad_etiqueta_original": "Todas las edades",
    }
    rows = []
    for metrica, valor in (("nacimientos", births), ("defunciones", deaths)):
        if valor is not None:
            row = dict(common)
            row.update({"metrica": metrica, "unidad": metrica, "codigo_serie": metrica, "valor": valor})
            rows.append(row)
    return rows


def silver_frame(rows):
    return frame_from(rows)
