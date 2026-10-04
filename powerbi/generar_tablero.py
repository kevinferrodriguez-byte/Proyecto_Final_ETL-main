from pathlib import Path
import json
import os
import stat
import time
import sys
import uuid

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi"
NAME = "Pensiones_Espana"
CSV_DIR = ROOT / "data" / "serving" / "csv"
MODEL = OUT / f"{NAME}.SemanticModel"
REPORT = OUT / f"{NAME}.Report"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
VERSIONS = {"visual": "2.4.0", "page": "2.0.0", "report": "3.0.0"}
NAMESPACE = uuid.UUID("6b2f1c3a-8a1e-4f43-9d55-0d0f6c1a2b3c")

# ── Sistema visual (docs/13 §7) ────────────────────────────────────────────
C = {
    "canvas": "#F4F5F7", "surface": "#FFFFFF", "border": "#E1E4E8", "text": "#1F2328", "text2": "#57606A", "muted": "#8C959F",
    "brand": "#1C4E80", "observed": "#2A78D6", "compare": "#EB6834", "third": "#1BAF7A", "reference": "#8C959F",
    "good": "#1A7F37", "bad": "#CF222E", "warning": "#9A6700", "women": "#EB6834", "men": "#2A78D6", "total": "#57606A",
}
PALETTE = ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4", "#008300", "#7A5BD6", "#8C959F"]
FONT, FONT_BOLD = "Segoe UI", "Segoe UI Semibold"
W, H, M, G = 1280, 720, 24, 16  # lienzo, margen, separación

TABLES = [
    "dim_tiempo", "dim_territorio", "dim_sexo", "dim_grupo_edad", "dim_fuente", "dim_indicador", "dim_escenario",
    "fact_indicadores_anual", "fact_proyecciones_demograficas", "dm_panel_anual", "dm_escenarios_2050",
    "aux_calidad_reglas", "aux_linaje",
]
SELECTOR = "sel_indicador_escenario"  # tabla desconectada para elegir el indicador en «Horizonte 2050»
SELECTOR_ROWS = [
    (1, "tasa_dependencia_mayores", "Dependencia de mayores (%)"),
    (2, "indice_envejecimiento", "Índice de envejecimiento"),
    (3, "porcentaje_mayores_65", "% población 65+"),
    (4, "tasa_dependencia", "Tasa de dependencia total (%)"),
]
RELATIONSHIPS = [
    ("fact_indicadores_anual", "tiempo_key", "dim_tiempo"), ("fact_indicadores_anual", "territorio_key", "dim_territorio"),
    ("fact_indicadores_anual", "sexo_key", "dim_sexo"), ("fact_indicadores_anual", "grupo_edad_key", "dim_grupo_edad"),
    ("fact_indicadores_anual", "indicador_key", "dim_indicador"), ("fact_indicadores_anual", "fuente_key", "dim_fuente"),
    ("fact_proyecciones_demograficas", "tiempo_key", "dim_tiempo"), ("fact_proyecciones_demograficas", "territorio_key", "dim_territorio"),
    ("fact_proyecciones_demograficas", "escenario_key", "dim_escenario"), ("fact_proyecciones_demograficas", "sexo_key", "dim_sexo"),
    ("fact_proyecciones_demograficas", "grupo_edad_key", "dim_grupo_edad"), ("fact_proyecciones_demograficas", "indicador_key", "dim_indicador"),
    ("fact_proyecciones_demograficas", "fuente_key", "dim_fuente"),
    ("dm_panel_anual", "tiempo_key", "dim_tiempo"), ("dm_panel_anual", "territorio_key", "dim_territorio"),
]
TEXT_COLUMNS = {"fecha_generacion"}  # marcas de tiempo técnicas: se cargan como texto
F = "fact_indicadores_anual"
P = "fact_proyecciones_demograficas"
Q = "aux_calidad_reglas"
TOTAL = 'dim_sexo[codigo_sexo] = "total", dim_grupo_edad[codigo_grupo] = "total"'


def guid(*parts):
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


def ident(name):
    return f"'{name}'" if any(not (ch.isalnum() or ch == "_") for ch in name) or name[0].isdigit() else name


# ════════════════════════════════════════════════════════════════════════════
# MEDIDAS DAX
# ════════════════════════════════════════════════════════════════════════════
def by_code(code, extra=TOTAL):
    return f'CALCULATE([Valor observado], dim_indicador[codigo_indicador] = "{code}", {extra})'


def latest(measure, code):
    return f'VAR ultimo = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = "{code}") RETURN CALCULATE([{measure}], dim_tiempo[tiempo_key] = ultimo)'


def first_last(code, alias=""):
    """Variables DAX: primer y último año con dato del indicador dentro del periodo seleccionado."""
    return (
        f'VAR a0{alias} = CALCULATE(MIN({F}[tiempo_key]), dim_indicador[codigo_indicador] = "{code}", ALLSELECTED(dim_tiempo)) '
        f'VAR a1{alias} = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = "{code}", ALLSELECTED(dim_tiempo)) '
    )


# (nombre de la medida, código del indicador, formato, carpeta)
SERIES = [
    ("KPI-01 Índice de envejecimiento", "indice_envejecimiento", "0.0", "KPI"),
    ("KPI-02 Tasa de dependencia", "tasa_dependencia", "0.0", "KPI"),
    ("KPI-03 Dependencia de mayores", "tasa_dependencia_mayores", "0.0", "KPI"),
    ("KPI-04 Fecundidad (hijos por mujer)", "indicador_coyuntural_fecundidad", "0.00", "KPI"),
    ("KPI-05 Saldo vegetativo", "saldo_vegetativo", "#,0", "KPI"),
    ("KPI-06 Saldo migratorio exterior", "saldo_migratorio_exterior", "#,0", "KPI"),
    ("KPI-07 Afiliados por pensión", "ratio_cotizantes_pensionistas", "0.00", "KPI"),
    ("KPI-08 Gasto en pensiones % PIB", "gasto_pensiones_pib", "0.0", "KPI"),
    ("% población 65+", "porcentaje_mayores_65", "0.0", "Contexto"),
    ("Esperanza de vida al nacer", "esperanza_vida_nacimiento", "0.00", "Contexto"),
    ("Tasa de afiliación 16-64", "tasa_afiliacion_16_64", "0.0", "Contexto"),
    ("Pensión media mensual (€)", "pension_media_mensual", "#,0", "Contexto"),
    ("Población total", "poblacion", "#,0", "Métricas base"),
    ("Afiliados a 31 de diciembre", "total_afiliados", "#,0", "Métricas base"),
    ("Pensiones contributivas", "total_pensiones", "#,0", "Métricas base"),
    ("Nómina mensual de pensiones (miles €)", "importe_nomina_pensiones", "#,0", "Métricas base"),
    ("PIB (M€)", "pib", "#,0", "Métricas base"),
    ("Gasto en pensiones (M€)", "gasto_pensiones", "#,0", "Métricas base"),
]
CODE = {name: code for name, code, *_ in SERIES}
LATEST = {name: f"{name.split(' ', 1)[0] if name.startswith('KPI') else name} · último" for name, *_ in SERIES}

# Tarjetas: (clave, etiqueta visible, medida del valor, código para el contexto, formato del valor)
CARDS = {
    "kpi03": ("Dependencia de mayores (%)", LATEST["KPI-03 Dependencia de mayores"], "tasa_dependencia_mayores"),
    "kpi07": ("Afiliados por pensión contributiva", LATEST["KPI-07 Afiliados por pensión"], "ratio_cotizantes_pensionistas"),
    "kpi08": ("Gasto en pensiones (% del PIB)", LATEST["KPI-08 Gasto en pensiones % PIB"], "gasto_pensiones_pib"),
    "kpi01": ("Índice de envejecimiento", LATEST["KPI-01 Índice de envejecimiento"], "indice_envejecimiento"),
    "kpi04": ("Fecundidad (hijos por mujer)", LATEST["KPI-04 Fecundidad (hijos por mujer)"], "indicador_coyuntural_fecundidad"),
    "p65": ("Población de 65+ (%)", LATEST["% población 65+"], "porcentaje_mayores_65"),
    "afiliacion": ("Afiliados por 100 personas de 16-64", LATEST["Tasa de afiliación 16-64"], "tasa_afiliacion_16_64"),
    "afiliados": ("Afiliados a 31/12 (millones)", "Afiliados (millones) · último", "total_afiliados"),
    "pensiones": ("Pensiones contributivas (millones)", "Pensiones (millones) · último", "total_pensiones"),
    "gasto": ("Gasto en pensiones (miles de M€)", "Gasto en pensiones (miles de M€) · último", "gasto_pensiones"),
    "media": ("Pensión media mensual (€)", LATEST["Pensión media mensual (€)"], "pension_media_mensual"),
    "nomina": ("Nómina mensual (miles de M€)", "Nómina mensual (miles de M€) · último", "importe_nomina_pensiones"),
}


def fact_measures():
    m = [("Valor observado", f"SUM({F}[valor])", "#,0.00", "Base")]
    for name, code, fmt, folder in SERIES:
        m.append((name, by_code(code), fmt, folder))
        m.append((LATEST[name], latest(name, code), fmt, "Último valor"))
    m += [
        ("Esperanza de vida a los 65 (por sexo)", by_code("esperanza_vida_65", 'dim_grupo_edad[codigo_grupo] = "total"'), "0.0", "Contexto"),
        ("Población por grupo de edad", 'CALCULATE([Valor observado], dim_indicador[codigo_indicador] = "poblacion", dim_sexo[codigo_sexo] = "total", KEEPFILTERS(dim_grupo_edad[codigo_grupo] <> "total"))', "#,0", "Métricas base"),
        ("Dependencia juvenil", 'VAR total = [KPI-02 Tasa de dependencia] VAR mayores = [KPI-03 Dependencia de mayores] RETURN IF(ISBLANK(total) || ISBLANK(mayores), BLANK(), total - mayores)', "0.0", "Contexto"),
        ("Afiliados (millones) · último", f'DIVIDE([{LATEST["Afiliados a 31 de diciembre"]}], 1000000)', "0.00", "Último valor"),
        ("Pensiones (millones) · último", f'DIVIDE([{LATEST["Pensiones contributivas"]}], 1000000)', "0.00", "Último valor"),
        ("Gasto en pensiones (miles de M€) · último", f'DIVIDE([{LATEST["Gasto en pensiones (M€)"]}], 1000)', "#,0.0", "Último valor"),
        ("Nómina mensual (miles de M€) · último", f'DIVIDE([{LATEST["Nómina mensual de pensiones (miles €)"]}], 1000000)', "#,0.00", "Último valor"),
        # Referencias de lectura (series grises discontinuas)
        ("Umbral de reemplazo (2,1)", 'IF(ISBLANK([KPI-04 Fecundidad (hijos por mujer)]), BLANK(), 2.1)', "0.0", "Referencias"),
        # Índices base 100 (comparar magnitudes distintas en un solo eje)
        ("Año base contributivo", f'CALCULATE(MIN({F}[tiempo_key]), dim_indicador[codigo_indicador] = "total_pensiones", ALLSELECTED(dim_tiempo))', "0", "Índices"),
        ("Afiliados (índice)", 'VAR a0 = [Año base contributivo] VAR base = CALCULATE([Afiliados a 31 de diciembre], REMOVEFILTERS(dim_tiempo), dim_tiempo[tiempo_key] = a0) RETURN IF(MAX(dim_tiempo[anyo]) >= a0, DIVIDE([Afiliados a 31 de diciembre], base) * 100)', "0.0", "Índices"),
        ("Pensiones (índice)", 'VAR a0 = [Año base contributivo] VAR base = CALCULATE([Pensiones contributivas], REMOVEFILTERS(dim_tiempo), dim_tiempo[tiempo_key] = a0) RETURN IF(MAX(dim_tiempo[anyo]) >= a0, DIVIDE([Pensiones contributivas], base) * 100)', "0.0", "Índices"),
        ("Base 100 (contributivo)", 'IF(ISBLANK([Pensiones (índice)]), BLANK(), 100)', "0", "Referencias"),
        ("Año base financiero", f'CALCULATE(MIN({F}[tiempo_key]), dim_indicador[codigo_indicador] = "gasto_pensiones_pib", ALLSELECTED(dim_tiempo))', "0", "Índices"),
        ("Gasto en pensiones (índice)", 'VAR a0 = [Año base financiero] VAR base = CALCULATE([Gasto en pensiones (M€)], REMOVEFILTERS(dim_tiempo), dim_tiempo[tiempo_key] = a0) RETURN IF(MAX(dim_tiempo[anyo]) >= a0, DIVIDE([Gasto en pensiones (M€)], base) * 100)', "0.0", "Índices"),
        ("PIB (índice)", 'VAR a0 = [Año base financiero] VAR base = CALCULATE([PIB (M€)], REMOVEFILTERS(dim_tiempo), dim_tiempo[tiempo_key] = a0) RETURN IF(MAX(dim_tiempo[anyo]) >= a0 && NOT ISBLANK([Gasto en pensiones (M€)]), DIVIDE([PIB (M€)], base) * 100)', "0.0", "Índices"),
        ("Base 100 (financiero)", 'IF(ISBLANK([PIB (índice)]), BLANK(), 100)', "0", "Referencias"),
        # Contexto genérico de un indicador (se evalúa con dim_indicador filtrado a una fila)
        ("Año del último valor", f"CALCULATE(MAX({F}[tiempo_key]), {TOTAL})", "0", "Contexto KPI"),
        ("Último valor", f"VAR a = [Año del último valor] RETURN CALCULATE([Valor observado], dim_tiempo[tiempo_key] = a, {TOTAL})", "#,0.00", "Contexto KPI"),
        ("Valor año anterior", f"VAR a = [Año del último valor] RETURN CALCULATE([Valor observado], dim_tiempo[tiempo_key] = a - 1, {TOTAL})", "#,0.00", "Contexto KPI"),
        ("Variación absoluta", 'VAR v = [Último valor] VAR p = [Valor año anterior] RETURN IF(ISBLANK(v) || ISBLANK(p), BLANK(), v - p)', "#,0.00", "Contexto KPI"),
        ("Variación (texto)",
         'VAR d = [Variación absoluta] VAR p = [Valor año anterior] VAR codigo = SELECTEDVALUE(dim_indicador[codigo_indicador]) '
         'VAR unidad = SELECTEDVALUE(dim_indicador[unidad]) VAR anterior = [Año del último valor] - 1 '
         'VAR flecha = IF(d > 0, "▲ ", IF(d < 0, "▼ ", "■ ")) '
         'VAR cifra = SWITCH(TRUE(), unidad IN {"porcentaje", "porcentaje_pib"}, FORMAT(d, "+0.0;-0.0;0.0") & " pp", '
         'codigo IN {"saldo_vegetativo", "saldo_migratorio_exterior"}, FORMAT(d, "+#,0;-#,0;0"), '
         'unidad IN {"hijos_por_mujer", "afiliados_por_pension", "anos"}, FORMAT(d, "+0.00;-0.00;0.00"), '
         'FORMAT(DIVIDE(d, ABS(p)), "+0.0%;-0.0%;0.0%")) '
         'RETURN IF(ISBLANK(d), "Sin dato del año anterior", flecha & cifra & " vs " & anterior)', None, "Contexto KPI"),
        ("Lectura de la variación",
         'VAR d = [Variación absoluta] VAR s = SELECTEDVALUE(dim_indicador[sentido]) '
         'RETURN SWITCH(TRUE(), ISBLANK(d), BLANK(), d = 0 || s = "neutro", "neutral", '
         '(d > 0 && s = "mayor_es_mas_riesgo") || (d < 0 && s = "menor_es_mas_riesgo"), "desfavorable", "favorable")', None, "Contexto KPI"),
        ("Color de la variación", f'SWITCH([Lectura de la variación], "desfavorable", "{C["bad"]}", "favorable", "{C["good"]}", "{C["text2"]}")', None, "Contexto KPI"),
        ("Estado del último valor", f'VAR a = [Año del último valor] RETURN IF(CALCULATE(COUNTROWS({F}), dim_tiempo[tiempo_key] = a, {F}[estado_dato] = "provisional", {TOTAL}) > 0, "provisional", "definitivo")', None, "Contexto KPI"),
        ("Fuente (corta)", 'SWITCH(SELECTEDVALUE(dim_indicador[codigo_fuente]), "ine", "INE", "seguridad_social", "Seguridad Social", "eurostat", "Eurostat", "integrado", "INE + Seguridad Social", "")', None, "Contexto KPI"),
        ("Contexto del KPI",
         'VAR lectura = [Lectura de la variación] '
         'RETURN [Variación (texto)] & IF(ISBLANK(lectura) || lectura = "neutral", "", " (" & lectura & ")") & "  ·  dato " & [Año del último valor] '
         '& IF([Estado del último valor] = "provisional", " (provisional)", "") & "  ·  " & [Fuente (corta)]', None, "Contexto KPI"),
        ("Último valor (texto)",
         'VAR v = [Último valor] VAR u = SELECTEDVALUE(dim_indicador[unidad]) VAR codigo = SELECTEDVALUE(dim_indicador[codigo_indicador]) '
         'RETURN IF(ISBLANK(v), BLANK(), SWITCH(TRUE(), u IN {"porcentaje", "porcentaje_pib"}, FORMAT(v, "0.0") & " %", '
         'codigo IN {"saldo_vegetativo", "saldo_migratorio_exterior"}, FORMAT(v, "+#,0;-#,0"), u = "hijos_por_mujer", FORMAT(v, "0.00"), '
         'u = "afiliados_por_pension", FORMAT(v, "0.00"), u = "eur_mes", FORMAT(v, "#,0") & " €", FORMAT(v, "#,0.0")))', None, "Contexto KPI"),
        # Definición del indicador (página de tooltip)
        ("Def · indicador", 'SELECTEDVALUE(dim_indicador[nombre_indicador])', None, "Definiciones"),
        ("Def · fórmula", 'SELECTEDVALUE(dim_indicador[formula])', None, "Definiciones"),
        ("Def · unidad", 'SELECTEDVALUE(dim_indicador[unidad])', None, "Definiciones"),
        ("Def · fuente", 'SELECTEDVALUE(dim_fuente[organismo], [Fuente (corta)])', None, "Definiciones"),
        ("Def · cobertura", 'SELECTEDVALUE(dim_indicador[cobertura_desde]) & "–" & SELECTEDVALUE(dim_indicador[cobertura_hasta])', None, "Definiciones"),
        ("Def · descripción", 'SELECTEDVALUE(dim_indicador[descripcion])', None, "Definiciones"),
        ("Correlación dependencia-gasto",
         'VAR t = FILTER(ADDCOLUMNS(VALUES(dim_tiempo[anyo]), "@x", [KPI-03 Dependencia de mayores], "@y", [KPI-08 Gasto en pensiones % PIB]), NOT ISBLANK([@x]) && NOT ISBLANK([@y])) '
         'VAR mx = AVERAGEX(t, [@x]) VAR my = AVERAGEX(t, [@y]) '
         'RETURN DIVIDE(SUMX(t, ([@x] - mx) * ([@y] - my)), SQRT(SUMX(t, ([@x] - mx) ^ 2)) * SQRT(SUMX(t, ([@y] - my) ^ 2)))', "0.00", "Contexto"),
        ("Año de los datos", f"CALCULATE(MAX({F}[tiempo_key]), REMOVEFILTERS(dim_tiempo))", "0", "Títulos"),
        ("Subtítulo de los datos", f'"Datos observados hasta " & CALCULATE(MAX({F}[tiempo_key]), REMOVEFILTERS(dim_tiempo)) & "  ·  Fuentes oficiales: INE · Seguridad Social (TGSS/INSS) · Eurostat"', None, "Títulos"),
    ]
    for key, (_, _, code) in CARDS.items():
        m.append((f"Contexto · {key}", f'CALCULATE([Contexto del KPI], dim_indicador[codigo_indicador] = "{code}")', None, "Tarjetas"))
        m.append((f"Color · {key}", f'CALCULATE([Color de la variación], dim_indicador[codigo_indicador] = "{code}")', None, "Tarjetas"))
    m += title_measures()
    return m


def title_measures():
    """Títulos de hallazgo: las afirmaciones están condicionadas a que los datos las sostengan."""
    dep = "KPI-03 Dependencia de mayores"
    t = [
        ("Título · dependencia",
         first_last("tasa_dependencia_mayores") + f'VAR v0 = CALCULATE([{dep}], dim_tiempo[tiempo_key] = a0) VAR v1 = CALCULATE([{dep}], dim_tiempo[tiempo_key] = a1) '
         'RETURN "La dependencia de mayores " & IF(v1 >= 2 * v0, "se duplicó", IF(v1 >= 1.95 * v0, "prácticamente se duplicó", IF(v1 > v0, "aumentó", "bajó"))) & ": de " & FORMAT(v0, "0.0") & " % (" & a0 & ") a " & FORMAT(v1, "0.0") & " % (" & a1 & ")"'),
        ("Título · estructura",
         first_last("porcentaje_mayores_65") + 'VAR v0 = CALCULATE([% población 65+], dim_tiempo[tiempo_key] = a0) VAR v1 = CALCULATE([% población 65+], dim_tiempo[tiempo_key] = a1) '
         'RETURN "Las personas de 65+ pasan del " & FORMAT(v0, "0.0") & " % al " & FORMAT(v1, "0.0") & " % de la población (" & a0 & "–" & a1 & ")"'),
        ("Título · fecundidad",
         first_last("indicador_coyuntural_fecundidad") + f'VAR v1 = CALCULATE([KPI-04 Fecundidad (hijos por mujer)], dim_tiempo[tiempo_key] = a1) '
         f'VAR vmin = CALCULATE(MIN({F}[valor]), dim_indicador[codigo_indicador] = "indicador_coyuntural_fecundidad", ALLSELECTED(dim_tiempo)) '
         'RETURN IF(v1 <= vmin, "La fecundidad marca su mínimo del periodo: ", "Fecundidad: ") & FORMAT(v1, "0.00") & " hijos por mujer en " & a1 & IF(v1 < 2.1, ", por debajo del reemplazo (2,1)", "")'),
        ("Título · saldo vegetativo",
         first_last("saldo_vegetativo") + 'VAR v1 = CALCULATE([KPI-05 Saldo vegetativo], dim_tiempo[tiempo_key] = a1) '
         f'VAR ultimoPositivo = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = "saldo_vegetativo", {F}[valor] > 0, ALLSELECTED(dim_tiempo)) '
         'RETURN IF(v1 >= 0, "Saldo vegetativo positivo en " & a1, IF(ISBLANK(ultimoPositivo), "Saldo vegetativo negativo en todo el periodo", "Saldo vegetativo negativo desde " & (ultimoPositivo + 1) & ": mueren más personas de las que nacen"))'),
        ("Título · saldo migratorio",
         first_last("saldo_migratorio_exterior") + 'VAR v1 = CALCULATE([KPI-06 Saldo migratorio exterior], dim_tiempo[tiempo_key] = a1) '
         'RETURN "Saldo migratorio con el extranjero: " & FORMAT(v1, "+#,0;-#,0") & " en " & a1'),
        ("Título · índice contributivo",
         'VAR a0 = [Año base contributivo] '
         f'VAR a1 = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = "total_pensiones", ALLSELECTED(dim_tiempo)) '
         'VAR ga = DIVIDE(CALCULATE([Afiliados a 31 de diciembre], dim_tiempo[tiempo_key] = a1), CALCULATE([Afiliados a 31 de diciembre], dim_tiempo[tiempo_key] = a0)) - 1 '
         'VAR gp = DIVIDE(CALCULATE([Pensiones contributivas], dim_tiempo[tiempo_key] = a1), CALCULATE([Pensiones contributivas], dim_tiempo[tiempo_key] = a0)) - 1 '
         'RETURN "Desde " & a0 & ", los afiliados " & IF(ga > gp, "crecen más que las pensiones", "no crecen más que las pensiones") & ": " & FORMAT(ga, "+0%;-0%") & " frente a " & FORMAT(gp, "+0%;-0%") & " (" & a1 & ")"'),
        ("Título · ratio",
         first_last("ratio_cotizantes_pensionistas") + 'VAR v0 = CALCULATE([KPI-07 Afiliados por pensión], dim_tiempo[tiempo_key] = a0) VAR v1 = CALCULATE([KPI-07 Afiliados por pensión], dim_tiempo[tiempo_key] = a1) '
         'RETURN "Afiliados por pensión: de " & FORMAT(v0, "0.00") & " (" & a0 & ") a " & FORMAT(v1, "0.00") & " (" & a1 & ")"'),
        ("Título · afiliación",
         first_last("tasa_afiliacion_16_64") + 'VAR v1 = CALCULATE([Tasa de afiliación 16-64], dim_tiempo[tiempo_key] = a1) '
         f'VAR vmax = CALCULATE(MAX({F}[valor]), dim_indicador[codigo_indicador] = "tasa_afiliacion_16_64", ALLSELECTED(dim_tiempo)) '
         'RETURN FORMAT(v1, "0.0") & " afiliados por cada 100 personas de 16-64 años en " & a1 & IF(v1 >= vmax, ": máximo del periodo", "")'),
        ("Título · esperanza de vida 65",
         f'VAR a = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = "esperanza_vida_65", ALLSELECTED(dim_tiempo)) '
         'VAR mujeres = CALCULATE([Esperanza de vida a los 65 (por sexo)], dim_sexo[codigo_sexo] = "mujeres", dim_tiempo[tiempo_key] = a) '
         'VAR hombres = CALCULATE([Esperanza de vida a los 65 (por sexo)], dim_sexo[codigo_sexo] = "hombres", dim_tiempo[tiempo_key] = a) '
         'RETURN "A los 65 años, las mujeres viven en promedio " & FORMAT(mujeres - hombres, "0.0") & " años más que los hombres (" & a & ")"'),
        ("Título · gasto",
         first_last("gasto_pensiones_pib") + 'VAR v0 = CALCULATE([KPI-08 Gasto en pensiones % PIB], dim_tiempo[tiempo_key] = a0) VAR v1 = CALCULATE([KPI-08 Gasto en pensiones % PIB], dim_tiempo[tiempo_key] = a1) '
         f'VAR vmax = CALCULATE(MAX({F}[valor]), dim_indicador[codigo_indicador] = "gasto_pensiones_pib", ALLSELECTED(dim_tiempo)) '
         f'VAR amax = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = "gasto_pensiones_pib", {F}[valor] = vmax, ALLSELECTED(dim_tiempo)) '
         'RETURN "Gasto en pensiones: de " & FORMAT(v0, "0.0") & " % a " & FORMAT(v1, "0.0") & " % del PIB (" & a0 & "–" & a1 & ")" & IF(amax <> a1, "; máximo de " & FORMAT(vmax, "0.0") & " % en " & amax, "")'),
        ("Título · índice financiero",
         'VAR a0 = [Año base financiero] '
         f'VAR a1 = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = "gasto_pensiones_pib", ALLSELECTED(dim_tiempo)) '
         'VAR gg = DIVIDE(CALCULATE([Gasto en pensiones (M€)], dim_tiempo[tiempo_key] = a1), CALCULATE([Gasto en pensiones (M€)], dim_tiempo[tiempo_key] = a0)) - 1 '
         'VAR gp = DIVIDE(CALCULATE([PIB (M€)], dim_tiempo[tiempo_key] = a1), CALCULATE([PIB (M€)], dim_tiempo[tiempo_key] = a0)) - 1 '
         'RETURN "Entre " & a0 & " y " & a1 & " el gasto en pensiones creció " & FORMAT(gg, "+0%;-0%") & " y el PIB " & FORMAT(gp, "+0%;-0%") & " (en euros corrientes)"'),
        ("Título · dispersión",
         first_last("gasto_pensiones_pib") + 'VAR r = [Correlación dependencia-gasto] '
         'RETURN "Más dependencia de mayores se asocia a más gasto/PIB: correlación de " & FORMAT(r, "0.00") & " (" & a0 & "–" & a1 & ")"'),
        ("Título · pensión media",
         first_last("pension_media_mensual") + 'VAR v0 = CALCULATE([Pensión media mensual (€)], dim_tiempo[tiempo_key] = a0) VAR v1 = CALCULATE([Pensión media mensual (€)], dim_tiempo[tiempo_key] = a1) '
         'RETURN "La pensión media pasa de " & FORMAT(v0, "#,0") & " € a " & FORMAT(v1, "#,0") & " € al mes (" & a0 & "–" & a1 & ", euros corrientes)"'),
        ("Título · calidad",
         '[Reglas superadas] & " de " & [Reglas evaluadas] & " reglas de calidad superadas · " & [Reglas con advertencia] & " advertencias · " & [Reglas con falla] & " fallas"'),
    ]
    return [(name, dax, None, "Títulos") for name, dax in t]


def projection_measures():
    sel = f'SELECTEDVALUE({SELECTOR}[codigo], "tasa_dependencia_mayores")'
    m = [
        ("Valor proyectado", f"SUM({P}[valor])", "#,0.00", "Base"),
        ("Indicador seleccionado", sel, None, "Escenarios INE"),
        ("Observado (selección)", f'VAR c = {sel} RETURN CALCULATE([Valor observado], dim_indicador[codigo_indicador] = c, {TOTAL})', "0.0", "Escenarios INE"),
    ]
    for scenario in ("base", "optimista", "pesimista"):
        m.append((f"Escenario {scenario} (selección)",
                  f'VAR c = {sel} RETURN CALCULATE([Valor proyectado], dim_indicador[codigo_indicador] = c, {TOTAL}, dim_escenario[escenario_kr] = "{scenario}")', "0.0", "Escenarios INE"))
    m += [
        ("Proyección 2050 (selección)", f'VAR c = {sel} RETURN CALCULATE([Valor proyectado], dim_indicador[codigo_indicador] = c, {TOTAL}, dim_tiempo[anyo] = 2050)', "0.0", "Escenarios INE"),
        ("Último observado (selección)", f'VAR c = {sel} VAR a = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = c, REMOVEFILTERS(dim_tiempo)) RETURN CALCULATE([Valor observado], dim_indicador[codigo_indicador] = c, {TOTAL}, dim_tiempo[tiempo_key] = a)', "0.0", "Escenarios INE"),
        ("Contexto · último observado", f'VAR c = {sel} VAR a = CALCULATE(MAX({F}[tiempo_key]), dim_indicador[codigo_indicador] = c, REMOVEFILTERS(dim_tiempo)) RETURN "Último dato observado (" & a & ") · INE"', None, "Escenarios INE"),
        ("Título · escenarios",
         f'VAR nombre = SELECTEDVALUE({SELECTOR}[nombre], "Dependencia de mayores (%)") '
         'VAR vmin = MINX(ALL(dim_escenario), [Proyección 2050 (selección)]) VAR vmax = MAXX(ALL(dim_escenario), [Proyección 2050 (selección)]) '
         'RETURN nombre & ": en 2050, entre " & FORMAT(vmin, "0.0") & " y " & FORMAT(vmax, "0.0") & " en los 8 escenarios oficiales del INE"', None, "Títulos"),
    ]
    return m


QUALITY_MEASURES = [
    ("Reglas evaluadas", f"COUNTROWS({Q})", "#,0", None),
    ("Reglas superadas", f'CALCULATE(COUNTROWS({Q}), {Q}[resultado] = "cumple") + 0', "#,0", None),
    ("Reglas con falla", f'CALCULATE(COUNTROWS({Q}), {Q}[resultado] = "falla") + 0', "#,0", None),
    ("Reglas con advertencia", f'CALCULATE(COUNTROWS({Q}), {Q}[resultado] = "advertencia") + 0', "#,0", None),
]
MEASURES = {F: fact_measures(), P: projection_measures(), Q: QUALITY_MEASURES}


# ════════════════════════════════════════════════════════════════════════════
# MODELO SEMÁNTICO (TMDL)
# ════════════════════════════════════════════════════════════════════════════
def column_types():
    """Tipos de cada columna desde los Parquet de Oro / CSV publicados por la carga."""
    types = {}
    for table in TABLES:
        frame = pd.read_csv(CSV_DIR / f"{table}.csv", encoding="utf-8-sig", nrows=200)
        parquet = next((ROOT / "data" / "gold").rglob(f"{table}.parquet"), None)
        dtypes = pd.read_parquet(parquet).dtypes if parquet else frame.dtypes
        types[table] = {column: kind(column, dtypes.get(column, frame[column].dtype)) for column in frame.columns}
    return types


def kind(column, dtype):
    text = str(dtype)
    if column in TEXT_COLUMNS:
        return "string"
    if "date32" in text:
        return "date"
    if text in ("bool", "boolean"):
        return "boolean"
    if text.lower().startswith("int"):
        return "int64"
    if text.startswith("float"):
        return "double"
    return "string"


TMDL_TYPES = {"int64": "int64", "double": "double", "boolean": "boolean", "date": "dateTime", "string": "string"}
M_TYPES = {"int64": "Int64.Type", "double": "type number", "boolean": "type logical", "date": "type date", "string": "type text"}


def measures_tmdl(table):
    lines = []
    for name, dax, fmt, folder in MEASURES.get(table, []):
        lines.append(f"\tmeasure {ident(name)} = {dax}")
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        if folder:
            lines.append(f"\t\tdisplayFolder: {folder}")
        lines += [f"\t\tlineageTag: {guid('measure', table, name)}", ""]
    return lines


def column_tmdl(table, column, data_type, sort_by=None):
    lines = [f"\tcolumn {ident(column)}", f"\t\tdataType: {TMDL_TYPES[data_type]}"]
    if data_type == "date":
        lines.append("\t\tformatString: yyyy-mm-dd")
    if column.endswith("_key") and not table.startswith("dim_"):
        lines.append("\t\tisHidden")
    lines += [f"\t\tlineageTag: {guid('column', table, column)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {column}"]
    if sort_by:
        lines.append(f"\t\tsortByColumn: {sort_by}")
    return lines + ["", "\t\tannotation SummarizationSetBy = Automatic", ""]


def partition_tmdl(table, source_lines):
    return [f"\tpartition {table} = m", "\t\tmode: import", "\t\tsource =", *[f"\t\t\t\t{line}" for line in source_lines], "", "\tannotation PBI_ResultType = Table", ""]


def table_tmdl(table, columns):
    lines = [f"table {table}", f"\tlineageTag: {guid('table', table)}", ""] + measures_tmdl(table)
    for column, data_type in columns.items():
        lines += column_tmdl(table, column, data_type, "indicador_key" if (table, column) == ("dim_indicador", "nombre_indicador") else None)
    conversions = ", ".join(f'{{"{column}", {M_TYPES[data_type]}}}' for column, data_type in columns.items())
    lines += partition_tmdl(table, [
        "let",
        f'    Origen = Csv.Document(File.Contents(RutaCSV & "{table}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),",
        f'    Tipos = Table.TransformColumnTypes(Encabezados, {{{conversions}}}, "en-US")',
        "in",
        "    Tipos",
    ])
    return "\n".join(lines)


def selector_tmdl():
    lines = [f"table {SELECTOR}", f"\tlineageTag: {guid('table', SELECTOR)}", ""]
    lines += column_tmdl(SELECTOR, "orden", "int64") + column_tmdl(SELECTOR, "codigo", "string") + column_tmdl(SELECTOR, "nombre", "string", "orden")
    rows = ", ".join(f'{{{order}, "{code}", "{name}"}}' for order, code, name in SELECTOR_ROWS)
    lines += partition_tmdl(SELECTOR, ["let", f"    Origen = #table(type table [orden = Int64.Type, codigo = text, nombre = text], {{{rows}}})", "in", "    Origen"])
    return "\n".join(lines)


def write_model(types):
    definition = MODEL / "definition"
    (definition / "tables").mkdir(parents=True)
    write_json(MODEL / "definition.pbism", {"$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "4.2", "settings": {}})
    write_text(definition / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    all_tables = TABLES + [SELECTOR]
    order = json.dumps(["RutaCSV", *all_tables], ensure_ascii=False)
    write_text(
        definition / "model.tmdl",
        "model Model\n\tculture: es-ES\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n\tsourceQueryCulture: es-ES\n"
        "\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        f"annotation PBI_QueryOrder = {order}\n\nannotation __PBI_TimeIntelligenceEnabled = 0\n\n"
        + "".join(f"ref table {table}\n" for table in all_tables),
    )
    path = str(CSV_DIR).rstrip("\\/") + "\\"
    write_text(
        definition / "expressions.tmdl",
        f'expression RutaCSV = "{path}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
        f"\tlineageTag: {guid('expression', 'RutaCSV')}\n\n\tannotation PBI_ResultType = Text\n",
    )
    rels = [f"relationship {guid('rel', source, column, target)}\n\tfromColumn: {source}.{column}\n\ttoColumn: {target}.{column}\n" for source, column, target in RELATIONSHIPS]
    write_text(definition / "relationships.tmdl", "\n".join(rels))
    for table, columns in types.items():
        write_text(definition / "tables" / f"{table}.tmdl", table_tmdl(table, columns))
    write_text(definition / "tables" / f"{SELECTOR}.tmdl", selector_tmdl())


# ════════════════════════════════════════════════════════════════════════════
# INFORME (PBIR)
# ════════════════════════════════════════════════════════════════════════════
def lit(value):
    if isinstance(value, bool):
        return {"expr": {"Literal": {"Value": "true" if value else "false"}}}
    if isinstance(value, (int, float)):
        return {"expr": {"Literal": {"Value": f"{value}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}}


def color(value):
    return {"solid": {"color": lit(value)}}


def measure_ref(table, name):
    return {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}}


def measure(table, name, display=None):
    projection = {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}, "queryRef": f"{table}.{name}", "nativeQueryRef": name}
    if display:
        projection["displayName"] = display
    return projection


def column(table, name, display=None):
    projection = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}, "queryRef": f"{table}.{name}", "nativeQueryRef": name}
    if display:
        projection["displayName"] = display
    return projection


def in_filter(name, table, field, values, negate=False):
    condition = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": field}}], "Values": [[lit(v)["expr"]] for v in values]}}
    if negate:
        condition = {"Not": {"Expression": condition}}
    return {
        "name": name,
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": field}},
        "type": "Categorical",
        "filter": {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}], "Where": [{"Condition": condition}]},
    }


def text_runs(paragraphs):
    """paragraphs: lista de párrafos; cada uno es una lista de (texto, estilo) o ("center", lista) para centrarlo."""
    result = []
    for paragraph in paragraphs:
        align, runs = paragraph if isinstance(paragraph, tuple) and isinstance(paragraph[0], str) and paragraph[0] in ("center", "right") else (None, paragraph)
        item = {"textRuns": [{"value": text, "textStyle": style} for text, style in runs]}
        if align:
            item["horizontalTextAlignment"] = align
        result.append(item)
    return result


STYLE_TITLE = {"fontFamily": FONT_BOLD, "fontSize": "18pt", "color": C["text"]}
STYLE_SUB = {"fontFamily": FONT, "fontSize": "10pt", "color": C["text2"]}
STYLE_BODY = {"fontFamily": FONT, "fontSize": "11pt", "color": C["text"]}
STYLE_BODY_BOLD = {"fontFamily": FONT_BOLD, "fontSize": "11pt", "color": C["text"]}
STYLE_NOTE = {"fontFamily": FONT, "fontSize": "9pt", "color": C["text2"], "fontStyle": "italic"}


class Page:
    def __init__(self, key, display, tooltip=False):
        self.key = key
        self.name = guid("page", key).replace("-", "")[:20]
        self.display = display
        self.tooltip = tooltip
        self.visuals = []
        self.no_interaction_sources = []

    def add(self, key, visual_type, roles, box, title=None, subtitle=None, sort=None, objects=None, filters=None, container=None, interactive=False, sync=None):
        x, y, width, height = box
        visual = {"visualType": visual_type, "drillFilterOtherVisuals": True}
        if roles is not None:
            visual["query"] = {"queryState": {role: {"projections": items} for role, items in roles.items()}}
            if sort:
                direction = sort.get("direction", "Ascending")
                visual["query"]["sortDefinition"] = {"sort": [{"field": sort["field"], "direction": direction}], "isDefaultSort": True}
        if objects:
            visual["objects"] = objects
        container_objects = dict(container or {})
        if title is not None:
            text = measure_ref(*title) if isinstance(title, tuple) else lit(title)
            container_objects["title"] = [{"properties": {"show": lit(True), "text": text, "fontSize": lit(12), "fontColor": color(C["text"]), "titleWrap": lit(True)}}]
        else:
            container_objects.setdefault("title", [{"properties": {"show": lit(False)}}])
        if subtitle:
            container_objects["subTitle"] = [{"properties": {"show": lit(True), "text": lit(subtitle), "fontSize": lit(9), "fontColor": color(C["text2"]), "titleWrap": lit(True)}}]
        visual["visualContainerObjects"] = container_objects
        if sync:
            visual["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
        name = guid("visual", self.name, key).replace("-", "")[:20]
        container_json = {
            "$schema": f"{SCHEMA}/item/report/definition/visualContainer/{VERSIONS['visual']}/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "z": len(self.visuals) * 1000, "width": width, "height": height, "tabOrder": len(self.visuals) * 1000},
            "visual": visual,
        }
        if filters:
            container_json["filterConfig"] = {"filters": filters}
        self.visuals.append(container_json)
        if not interactive:
            self.no_interaction_sources.append(name)
        return name

    def interactions(self):
        """Sin resaltado cruzado entre tarjetas y gráficos (comparten la dimensión tiempo); los segmentadores sí filtran."""
        names = [visual["name"] for visual in self.visuals]
        return [{"source": source, "target": target, "type": "NoFilter"} for source in self.no_interaction_sources for target in names if target != source]


# ── Componentes reutilizables (estilo: barra lateral, tarjetas redondeadas, encabezado amplio) ──
NAVY = "#0B2A4A"          # barra lateral y cifras principales
NAVY_TEXT = "#C9D6E6"     # texto sobre la barra lateral
NAVY_HOVER = "#16406B"
ICON_BG = "#EAF1FB"       # círculo de los iconos
INSIGHT_BG = "#EEF4FB"    # panel de hallazgos
SB = 216                  # ancho de la barra lateral
X0 = SB + M               # inicio del área de contenido
CW = W - X0 - M           # ancho del área de contenido (1016 px)
ICON_FONT = "Segoe MDL2 Assets"
GLYPH = {"personas": "", "contacto": "", "tarjeta": "", "calculadora": "", "calendario": "",
         "grafico": "", "ok": "", "aviso": "", "error": "", "idea": "", "info": ""}
NAV = [("resumen", "Resumen ejecutivo", "⌂"), ("demografia", "Presión demográfica", "◔"), ("contributivo", "Equilibrio contributivo", "⇄"),
       ("financiero", "Esfuerzo financiero", "€"), ("escenarios", "Horizonte 2050", "↗"), ("metodologia", "Metodología y calidad", "☰")]
FOOTER_NOTES = ("Notas: 2020 es una anomalía (COVID-19) · el saldo migratorio tiene ruptura de serie en 2021 · PIB y gasto/PIB recientes son provisionales · "
                "KPI-07 se mide por pensión, no por pensionista · los escenarios del INE son demográficos, no fiscales")


def page_name(key):
    return guid("page", key).replace("-", "")[:20]


def no_frame():
    return {"background": [{"properties": {"show": lit(False)}}], "border": [{"properties": {"show": lit(False)}}], "dropShadow": [{"properties": {"show": lit(False)}}]}


def frame(background, border=None, radius=12, padding=None):
    objects = {
        "background": [{"properties": {"show": lit(True), "color": color(background), "transparency": lit(0)}}],
        "border": [{"properties": {"show": lit(True), "color": color(border or background), "radius": lit(radius)}}],
        "dropShadow": [{"properties": {"show": lit(False)}}],
    }
    if padding is not None:
        objects["padding"] = [{"properties": {side: lit(padding) for side in ("top", "bottom", "left", "right")}}]
    return objects


def textbox(page, key, box, paragraphs, container=None):
    return page.add(key, "textbox", None, box, objects={"general": [{"properties": {"paragraphs": text_runs(paragraphs)}}]}, container=container or no_frame(), interactive=True)


def icon(page, key, box, glyph, background=ICON_BG, foreground=None, size="14pt"):
    textbox(page, key, box, [("center", [(GLYPH[glyph], {"fontFamily": ICON_FONT, "fontSize": size, "color": foreground or C["observed"]})])],
            container=frame(background, radius=box[2] // 2, padding=6))


def sidebar(page):
    textbox(page, "sb_panel", (0, 0, SB, H), [
        [("Pensiones en España", {"fontFamily": FONT_BOLD, "fontSize": "15pt", "color": "#FFFFFF"})],
        [("Riesgo demográfico y sostenibilidad del sistema público", {"fontFamily": FONT, "fontSize": "9pt", "color": NAVY_TEXT})],
    ], container={**frame(NAVY, radius=0, padding=16)})
    for position, (key, label, symbol) in enumerate(NAV):
        active = key == page.key
        fill = C["observed"] if active else NAVY
        foreground = "#FFFFFF" if active else NAVY_TEXT
        page.add(f"nav_{key}", "actionButton", None, (12, 104 + position * 46, SB - 24, 40),
                 objects={
                     "icon": [{"properties": {"shapeType": lit("blank")}, "selector": {"id": "default"}}],
                     "text": [{"properties": {"show": lit(True)}},
                              {"properties": {"text": lit(f"{symbol}   {label}"), "fontColor": color(foreground), "fontSize": lit(10.5),
                                              "fontFamily": lit(FONT_BOLD if active else FONT), "horizontalAlignment": lit("left"), "leftMargin": lit(12)},
                               "selector": {"id": "default"}}],
                     "fill": [{"properties": {"show": lit(True)}},
                              {"properties": {"fillColor": color(fill), "transparency": lit(0)}, "selector": {"id": "default"}},
                              {"properties": {"fillColor": color(C["observed"] if active else NAVY_HOVER), "transparency": lit(0)}, "selector": {"id": "hover"}}],
                     "outline": [{"properties": {"show": lit(False)}}],
                 },
                 container={**no_frame(), "visualLink": [{"properties": {"show": lit(True), "type": lit("PageNavigation"), "navigationSection": lit(page_name(key))}}]},
                 interactive=True)
    textbox(page, "sb_pie", (12, H - 132, SB - 24, 120), [
        [("Fuentes oficiales", {"fontFamily": FONT_BOLD, "fontSize": "9pt", "color": "#FFFFFF"})],
        [("INE · Seguridad Social (TGSS/INSS) · Eurostat", {"fontFamily": FONT, "fontSize": "8.5pt", "color": NAVY_TEXT})],
        [(" ", {"fontFamily": FONT, "fontSize": "6pt", "color": NAVY_TEXT})],
        [("Proyecto ETL · Grupo 5", {"fontFamily": FONT, "fontSize": "8pt", "color": "#8FA6C1"})],
        [("Universidad Autónoma de Occidente", {"fontFamily": FONT, "fontSize": "8pt", "color": "#8FA6C1"})],
    ])


def header(page, title, subtitle, slicer=False):
    textbox(page, "titulo", (X0, 8, 600, 88), [[(title, {"fontFamily": FONT_BOLD, "fontSize": "22pt", "color": NAVY})],
                                                [(subtitle, {"fontFamily": FONT, "fontSize": "11pt", "color": C["text2"]})]])
    x = X0 + CW - 196
    textbox(page, "act_fondo", (x, 18, 196, 68), [[("Datos observados hasta", {"fontFamily": FONT, "fontSize": "8.5pt", "color": C["text2"]})]],
            container=frame(C["surface"], C["border"]))
    icon(page, "act_icono", (x + 144, 30, 40, 40), "calendario")
    page.add("act_valor", "multiRowCard", {"Values": [measure(F, "Año de los datos")]}, (x + 4, 38, 130, 44),
             objects={"dataLabels": [{"properties": {"fontSize": lit(16), "color": color(NAVY), "fontFamily": lit(FONT_BOLD)}}],
                      "categoryLabels": [{"properties": {"show": lit(False)}}], "card": [{"properties": {"barShow": lit(False)}}]}, container=no_frame())
    if slicer:
        period_slicer(page, (x - G - 300, 18, 300, 68))


def footer(page, text=FOOTER_NOTES):
    textbox(page, "pie", (X0, H - 30, CW, 26), [[(text, {"fontFamily": FONT, "fontSize": "8pt", "color": C["muted"]})]])


def kpi_card(page, key, box, label, value_measure, context_measure=None, color_measure=None, glyph=None, table=F, value_size=26):
    """Tarjeta blanca redondeada: etiqueta + icono, cifra grande alineada a la izquierda y línea de contexto coloreada."""
    x, y, width, height = box
    textbox(page, f"{key}_fondo", box, [[(label, {"fontFamily": FONT_BOLD, "fontSize": "10pt", "color": C["text"]})]], container=frame(C["surface"], C["border"]))
    if glyph:
        icon(page, f"{key}_icono", (x + width - 54, y + 12, 40, 40), glyph)
    context_height = 30 if context_measure else 0
    page.add(f"{key}_valor", "multiRowCard", {"Values": [measure(table, value_measure)]}, (x + 4, y + 40, width - 64, height - 44 - context_height),
             objects={"dataLabels": [{"properties": {"fontSize": lit(value_size), "color": color(NAVY), "fontFamily": lit(FONT_BOLD)}}],
                      "categoryLabels": [{"properties": {"show": lit(False)}}], "card": [{"properties": {"barShow": lit(False)}}]}, container=no_frame())
    if context_measure:
        text_color = {"solid": {"color": measure_ref(table, color_measure)}} if color_measure else color(C["text2"])
        page.add(f"{key}_contexto", "multiRowCard", {"Values": [measure(table, context_measure)]}, (x + 4, y + height - 36, width - 8, 32),
                 objects={"dataLabels": [{"properties": {"fontSize": lit(9), "color": text_color, "fontFamily": lit(FONT_BOLD)}}],
                          "categoryLabels": [{"properties": {"show": lit(False)}}], "card": [{"properties": {"barShow": lit(False)}}]}, container=no_frame())


CARD_GLYPH = {"kpi03": "personas", "kpi01": "personas", "p65": "personas", "kpi04": "contacto", "kpi07": "contacto", "afiliados": "contacto",
              "pensiones": "tarjeta", "afiliacion": "grafico", "kpi08": "calculadora", "gasto": "tarjeta", "media": "tarjeta", "nomina": "tarjeta"}


def kpi_row(page, keys, y=104, height=124):
    width = (CW - (len(keys) - 1) * G) / len(keys)
    for position, key in enumerate(keys):
        label, value_measure, _ = CARDS[key]
        kpi_card(page, key, (X0 + position * (width + G), y, width, height), label, value_measure, f"Contexto · {key}", f"Color · {key}", CARD_GLYPH[key])


def series_style(entries):
    """entries: lista de (queryRef, color, estilo de línea, grosor)."""
    return {
        "dataPoint": [{"properties": {"fill": color(hex_color)}, "selector": {"metadata": ref}} for ref, hex_color, _, _ in entries],
        "lineStyles": [{"properties": {"lineStyle": lit(style), "strokeWidth": lit(width)}, "selector": {"metadata": ref}} for ref, _, style, width in entries],
    }


def chart_objects(entries=None, legend=True, data_labels=False):
    objects = series_style(entries) if entries else {}
    objects["legend"] = [{"properties": {"show": lit(legend), "position": lit("Top"), "fontSize": lit(9), "labelColor": color(C["text2"])}}]
    objects["categoryAxis"] = [{"properties": {"fontSize": lit(9), "labelColor": color(C["text2"]), "showAxisTitle": lit(False), "gridlineShow": lit(False)}}]
    objects["valueAxis"] = [{"properties": {"fontSize": lit(9), "labelColor": color(C["text2"]), "showAxisTitle": lit(False), "gridlineColor": color(C["border"])}}]
    if data_labels:
        objects["labels"] = [{"properties": {"show": lit(True), "fontSize": lit(9), "color": color(C["text2"])}}]
    return objects


YEAR = column("dim_tiempo", "anyo", "Año")
YEAR_SORT = {"field": YEAR["field"]}


def period_slicer(page, box):
    page.add("periodo", "slicer", {"Values": [YEAR]}, box, title="Periodo observado",
             objects={"data": [{"properties": {"mode": lit("Between")}}], "header": [{"properties": {"show": lit(False)}}]},
             filters=[in_filter("solo_observado", "dim_tiempo", "es_observado", [True])], interactive=True, sync="periodo_observado")


def line(page, key, entries, box, title, subtitle=None, legend=True, series=None, visual_type="lineChart"):
    """entries: (tabla, medida, nombre visible, color, estilo, grosor)."""
    roles = {"Category": [YEAR], "Y": [measure(table, name, display) for table, name, display, *_ in entries]}
    if series:
        roles["Series"] = [series]
    styles = [(f"{table}.{name}", hex_color, style, width) for table, name, _, hex_color, style, width in entries] if not series else None
    page.add(key, visual_type, roles, box, title=title, subtitle=subtitle, sort=YEAR_SORT, objects=chart_objects(styles, legend))


def base_page(key, display, title, subtitle, slicer=False):
    page = Page(key, display)
    sidebar(page)
    header(page, title, subtitle, slicer)
    footer(page)
    return page


# ── Páginas ────────────────────────────────────────────────────────────────
TOP = 104          # inicio del contenido
ROW2 = 244         # segunda fila (tras las tarjetas)
BOTTOM = H - 36    # fin del contenido (deja sitio al pie)
HALF = (CW - G) / 2


def page_resumen():
    page = base_page("resumen", "Resumen ejecutivo", "Resumen ejecutivo", "Riesgo demográfico y sostenibilidad del sistema público de pensiones en España")
    width = (CW - 3 * G) / 4
    for position, (key, label) in enumerate([("kpi03", "Dependencia de mayores (%)"), ("kpi07", "Afiliados por pensión contributiva"),
                                             ("kpi08", "Gasto en pensiones (% del PIB)"), ("media", "Pensión media mensual (€)")]):
        kpi_card(page, f"hero_{key}", (X0 + position * (width + G), TOP, width, 124), label, CARDS[key][1], f"Contexto · {key}", f"Color · {key}", CARD_GLYPH[key], value_size=28)
    line(page, "evolucion", [(F, "KPI-03 Dependencia de mayores", "Dependencia de mayores (%)", C["observed"], "solid", 2.5)], (X0, ROW2, HALF, 232),
         (F, "Título · dependencia"), subtitle="Personas de 65+ por cada 100 de 16-64 años · INE", legend=False, visual_type="areaChart")
    page.add("matriz_kpis", "tableEx", {"Values": [
        column("dim_indicador", "codigo_kpi", "KPI"), column("dim_indicador", "nombre_indicador", "Indicador"),
        measure(F, "Último valor (texto)", "Último valor"), measure(F, "Año del último valor", "Año"),
        measure(F, "Variación (texto)", "Variación anual"), measure(F, "Lectura de la variación", "Lectura"),
    ]}, (X0 + HALF + G, ROW2, HALF, 232), title="Los 8 KPIs: último dato observado y variación anual",
        subtitle="La lectura depende del sentido de riesgo de cada indicador · cursor sobre un KPI: definición",
        sort={"field": column("dim_indicador", "codigo_kpi")["field"]},
        objects={"values": [{"properties": {"fontSize": lit(9), "fontColor": color(C["text"])}}],
                 "columnHeaders": [{"properties": {"fontSize": lit(9), "fontColor": color(C["text2"]), "backColor": color(C["canvas"])}}],
                 "grid": [{"properties": {"rowPadding": lit(4), "gridHorizontal": lit(True), "gridHorizontalColor": color(C["border"]), "gridVertical": lit(False)}}]},
        filters=[in_filter("solo_kpis", "dim_indicador", "tipo_indicador", ["kpi"])],
        container={"visualTooltip": [{"properties": {"show": lit(True), "type": lit("ReportPage"), "section": lit(page_name("tooltip"))}}]})
    panel_y = ROW2 + 232 + G
    panel_h = BOTTOM - panel_y
    textbox(page, "hallazgos_fondo", (X0, panel_y, CW, panel_h), [[(" ", {"fontFamily": FONT, "fontSize": "6pt", "color": NAVY})]], container=frame(INSIGHT_BG, "#D6E4F5"))
    icon(page, "hallazgos_icono", (X0 + 14, panel_y + 10, 32, 32), "idea", background=C["surface"], size="12pt")
    textbox(page, "hallazgos_titulo", (X0 + 52, panel_y + 6, 700, 40), [[("Hallazgos clave", {"fontFamily": FONT_BOLD, "fontSize": "13pt", "color": NAVY}),
                                                                        ("   calculados con los datos observados en cada actualización", {"fontFamily": FONT, "fontSize": "9pt", "color": C["text2"]})]])
    insights = ["Título · índice contributivo", "Título · gasto", "Título · fecundidad", "Título · saldo vegetativo"]
    card_w = (CW - 28 - 3 * 12) / 4
    for position, name in enumerate(insights):
        page.add(f"hallazgo{position}", "multiRowCard", {"Values": [measure(F, name)]}, (X0 + 14 + position * (card_w + 12), panel_y + 50, card_w, panel_h - 62),
                 objects={"dataLabels": [{"properties": {"fontSize": lit(10), "color": color(C["text"]), "fontFamily": lit(FONT)}}],
                          "categoryLabels": [{"properties": {"show": lit(False)}}],
                          "card": [{"properties": {"barShow": lit(True), "barColor": color(C["observed"]), "barWeight": lit(4)}}]},
                 container=frame(C["surface"], C["border"], radius=10))
    return page


def page_demografia():
    page = base_page("demografia", "Presión demográfica", "Presión demográfica", "¿Por qué hay cada vez más personas mayores por cada persona en edad de trabajar?", slicer=True)
    kpi_row(page, ["kpi01", "kpi03", "kpi04", "p65"])
    page.add("composicion", "stackedAreaChart", {"Category": [YEAR], "Y": [measure(F, "Dependencia juvenil", "Dependencia juvenil (0-15)"), measure(F, "KPI-03 Dependencia de mayores", "Dependencia de mayores (65+)")]},
             (X0, ROW2, 600, 222), title=(F, "Título · dependencia"),
             subtitle="Personas de 0-15 y de 65+ por cada 100 de 16-64. La altura total es la tasa de dependencia (KPI-02), que baja porque cae la juvenil.",
             sort=YEAR_SORT, objects=chart_objects([(f"{F}.Dependencia juvenil", C["compare"], "solid", 2), (f"{F}.KPI-03 Dependencia de mayores", C["observed"], "solid", 2)]))
    page.add("estructura", "hundredPercentStackedAreaChart", {"Category": [YEAR], "Y": [measure(F, "Población por grupo de edad", "Población")], "Series": [column("dim_grupo_edad", "descripcion", "Grupo de edad")]},
             (X0 + 600 + G, ROW2, CW - 600 - G, 222), title=(F, "Título · estructura"), subtitle="Composición de la población a 1 de enero por grupo de edad (%) · INE",
             sort=YEAR_SORT, objects=chart_objects())
    row3 = ROW2 + 222 + G
    line(page, "fecundidad", [(F, "KPI-04 Fecundidad (hijos por mujer)", "Fecundidad (hijos por mujer)", C["observed"], "solid", 2.5),
                              (F, "Umbral de reemplazo (2,1)", "Umbral de reemplazo (2,1)", C["reference"], "dashed", 1.5)],
         (X0, row3, 400, BOTTOM - row3), (F, "Título · fecundidad"), subtitle="Indicador coyuntural de fecundidad publicado por el INE")
    half = (CW - 400 - 2 * G) / 2
    page.add("vegetativo", "clusteredColumnChart", {"Category": [YEAR], "Y": [measure(F, "KPI-05 Saldo vegetativo", "Saldo vegetativo")]}, (X0 + 400 + G, row3, half, BOTTOM - row3),
             title=(F, "Título · saldo vegetativo"), subtitle="Nacimientos − defunciones (personas) · INE", sort=YEAR_SORT,
             objects=chart_objects([(f"{F}.KPI-05 Saldo vegetativo", C["compare"], "solid", 2)], legend=False))
    page.add("migratorio", "clusteredColumnChart", {"Category": [YEAR], "Y": [measure(F, "KPI-06 Saldo migratorio exterior", "Saldo migratorio")]}, (X0 + 400 + 2 * G + half, row3, half, BOTTOM - row3),
             title=(F, "Título · saldo migratorio"), subtitle="Ruptura de serie en 2021 (tablas INE 24309 → 69758)", sort=YEAR_SORT,
             objects=chart_objects([(f"{F}.KPI-06 Saldo migratorio exterior", C["observed"], "solid", 2)], legend=False))
    return page


def page_contributivo():
    page = base_page("contributivo", "Equilibrio contributivo", "Equilibrio contributivo", "¿Crecen más los afiliados que cotizan o las pensiones que se pagan?", slicer=True)
    kpi_row(page, ["kpi07", "afiliados", "pensiones", "afiliacion"])
    line(page, "indice", [(F, "Afiliados (índice)", "Afiliados", C["observed"], "solid", 2.5), (F, "Pensiones (índice)", "Pensiones", C["compare"], "solid", 2.5),
                          (F, "Base 100 (contributivo)", "Base 100", C["reference"], "dashed", 1.5)],
         (X0, ROW2, HALF, 222), (F, "Título · índice contributivo"), subtitle="Índice: primer año con datos de pensiones = 100 · stocks de diciembre · TGSS e INSS")
    line(page, "ratio", [(F, "KPI-07 Afiliados por pensión", "Afiliados por pensión", C["observed"], "solid", 2.5)], (X0 + HALF + G, ROW2, HALF, 222),
         (F, "Título · ratio"), subtitle="Afiliados en alta a 31/12 ÷ pensiones contributivas a 1/12 · se mide por pensión, no por pensionista", legend=False)
    row3 = ROW2 + 222 + G
    line(page, "afiliacion", [(F, "Tasa de afiliación 16-64", "Afiliados por 100 personas de 16-64", C["observed"], "solid", 2.5)], (X0, row3, HALF, BOTTOM - row3),
         (F, "Título · afiliación"), subtitle="Afiliados a 31/12 del año t ÷ población de 16-64 a 1/1 del año t+1 × 100 · no es una tasa de empleo", legend=False, visual_type="areaChart")
    page.add("ev65", "lineChart", {"Category": [YEAR], "Y": [measure(F, "Esperanza de vida a los 65 (por sexo)", "Esperanza de vida a los 65")], "Series": [column("dim_sexo", "nombre_sexo", "Sexo")]},
             (X0 + HALF + G, row3, HALF, BOTTOM - row3), title=(F, "Título · esperanza de vida 65"),
             subtitle="Años de vida restantes a los 65 · aproxima la duración media de una pensión de jubilación · INE", sort=YEAR_SORT, objects=chart_objects())
    return page


def page_financiero():
    page = base_page("financiero", "Esfuerzo financiero", "Esfuerzo financiero", "¿Cuánto pesa el gasto en pensiones en la economía y cómo ha evolucionado?", slicer=True)
    kpi_row(page, ["kpi08", "gasto", "media", "nomina"])
    line(page, "kpi08", [(F, "KPI-08 Gasto en pensiones % PIB", "Gasto en pensiones (% PIB)", C["observed"], "solid", 2.5)], (X0, ROW2, HALF, 222),
         (F, "Título · gasto"), subtitle="Gasto en pensiones ESSPROS ÷ PIB a precios corrientes · Eurostat · los últimos años son provisionales", legend=False, visual_type="areaChart")
    line(page, "indice_fin", [(F, "Gasto en pensiones (índice)", "Gasto en pensiones", C["observed"], "solid", 2.5), (F, "PIB (índice)", "PIB", C["compare"], "solid", 2.5),
                              (F, "Base 100 (financiero)", "Base 100", C["reference"], "dashed", 1.5)],
         (X0 + HALF + G, ROW2, HALF, 222), (F, "Título · índice financiero"), subtitle="Índice: primer año con gasto/PIB = 100 · euros corrientes · Eurostat")
    row3 = ROW2 + 222 + G
    page.add("dispersion", "scatterChart", {"Category": [YEAR], "X": [measure(F, "KPI-03 Dependencia de mayores", "Dependencia de mayores (%)")], "Y": [measure(F, "KPI-08 Gasto en pensiones % PIB", "Gasto en pensiones (% PIB)")]},
             (X0, row3, HALF, BOTTOM - row3), title=(F, "Título · dispersión"),
             subtitle="Cada punto es un año. Asociación descriptiva, no causalidad: el gasto/PIB también depende del PIB, de la revalorización y de la pensión media.",
             objects={"dataPoint": [{"properties": {"fill": color(C["observed"])}}], "categoryAxis": [{"properties": {"fontSize": lit(9), "showAxisTitle": lit(True)}}],
                      "valueAxis": [{"properties": {"fontSize": lit(9), "showAxisTitle": lit(True)}}], "categoryLabels": [{"properties": {"show": lit(True), "fontSize": lit(8)}}]})
    line(page, "media", [(F, "Pensión media mensual (€)", "Pensión media (€/mes)", C["observed"], "solid", 2.5)], (X0 + HALF + G, row3, HALF, BOTTOM - row3),
         (F, "Título · pensión media"), subtitle="Nómina de diciembre ÷ número de pensiones contributivas · sin pagas extraordinarias · INSS", legend=False)
    return page


def page_escenarios():
    page = base_page("escenarios", "Horizonte 2050", "Horizonte 2050", "¿Qué rango de presión demográfica proyectan los escenarios oficiales del INE?")
    textbox(page, "alcance", (X0, TOP, CW, 52), [[
        ("ⓘ Escenarios demográficos condicionales del INE (2026-2076). ", {**STYLE_BODY_BOLD, "fontSize": "10pt", "color": C["warning"]}),
        ("No son previsiones ni escenarios fiscales: no se proyectan empleo, cotizaciones, PIB ni gasto. Línea continua: observado · discontinua: base · punteadas: optimista y pesimista.",
         {**STYLE_BODY, "fontSize": "10pt"}),
    ]], container=frame("#FFF8E6", "#F2DFAE"))
    top = TOP + 52 + G
    page.add("selector", "slicer", {"Values": [column(SELECTOR, "nombre", "Indicador")]}, (X0, top, 236, 188), title="Indicador",
             objects={"selection": [{"properties": {"singleSelect": lit(True), "strictSingleSelect": lit(True)}}], "header": [{"properties": {"show": lit(False)}}],
                      "items": [{"properties": {"fontSize": lit(10)}}]}, interactive=True)
    kpi_card(page, "ultimo_obs", (X0, top + 188 + G, 236, 120), "Último dato observado", "Último observado (selección)", "Contexto · último observado", None, "calendario", table=P, value_size=24)
    nota_y = top + 188 + G + 120 + G
    textbox(page, "nota", (X0, nota_y, 236, BOTTOM - nota_y), [[("Lectura: ", STYLE_BODY_BOLD),
                                                              ("la distancia entre las líneas punteadas es el rango que el INE asocia a distintas hipótesis de fecundidad y migración. No es un intervalo de probabilidad.", STYLE_NOTE)]],
            container=frame(C["surface"], C["border"]))
    chart_x = X0 + 236 + G
    chart_w = 480
    entries = [(P, "Observado (selección)", "Observado", C["observed"], "solid", 3), (P, "Escenario base (selección)", "Escenario base", C["observed"], "dashed", 2),
               (P, "Escenario optimista (selección)", "Escenario optimista", C["third"], "dotted", 2), (P, "Escenario pesimista (selección)", "Escenario pesimista", C["compare"], "dotted", 2)]
    line(page, "proyeccion", entries, (chart_x, top, chart_w, BOTTOM - top), (P, "Título · escenarios"), subtitle="Observado 1971-2025 y Proyecciones de Población INE 2026-2076")
    page.add("barras_2050", "clusteredBarChart", {"Category": [column("dim_escenario", "etiqueta_ine", "Escenario INE")], "Y": [measure(P, "Proyección 2050 (selección)", "Valor en 2050")]},
             (chart_x + chart_w + G, top, X0 + CW - chart_x - chart_w - G, BOTTOM - top), title="Valor en 2050 en los 8 escenarios del INE",
             subtitle="Incluye los 5 escenarios de sensibilidad", sort={"field": measure(P, "Proyección 2050 (selección)")["field"], "direction": "Descending"},
             objects={**chart_objects([(f"{P}.Proyección 2050 (selección)", C["observed"], "solid", 2)], legend=False, data_labels=True),
                      "categoryAxis": [{"properties": {"fontSize": lit(9), "labelColor": color(C["text2"]), "showAxisTitle": lit(False), "maxMarginFactor": lit(55)}}]})
    return page


def page_metodologia():
    page = base_page("metodologia", "Metodología y calidad", "Metodología y calidad del dato", "¿Cómo se calcula cada indicador y cuán fiable es el dato?")
    width = (CW - 3 * G) / 4
    for position, (name, label, glyph) in enumerate([("Reglas evaluadas", "Reglas de calidad evaluadas", "grafico"), ("Reglas superadas", "Reglas superadas", "ok"),
                                                     ("Reglas con advertencia", "Advertencias", "aviso"), ("Reglas con falla", "Fallas", "error")]):
        kpi_card(page, f"q{position}", (X0 + position * (width + G), TOP, width, 96), label, name, glyph=glyph, table=Q, value_size=24)
    row2 = TOP + 96 + G
    page.add("por_capa", "hundredPercentStackedBarChart", {"Category": [column(Q, "capa", "Capa")], "Y": [measure(Q, "Reglas evaluadas", "Reglas")], "Series": [column(Q, "resultado", "Resultado")]},
             (X0, row2, 400, 236), title=(F, "Título · calidad"), subtitle="Última ejecución de cada capa del pipeline", objects=chart_objects(), interactive=True)
    page.add("advertencias", "tableEx", {"Values": [column(Q, "capa", "Capa"), column(Q, "regla", "Regla"), column(Q, "resultado", "Resultado"), column(Q, "detalle", "Detalle")]},
             (X0 + 400 + G, row2, CW - 400 - G, 236), title="Advertencias y fallas activas (las reglas superadas se omiten)",
             subtitle="Las advertencias no detienen el pipeline: señalan atípicos reales o diferencias entre fuentes para revisión humana",
             filters=[in_filter("sin_cumple", Q, "resultado", ["cumple"], negate=True)],
             objects={"values": [{"properties": {"fontSize": lit(9)}}], "columnHeaders": [{"properties": {"fontSize": lit(9), "fontColor": color(C["text2"]), "backColor": color(C["canvas"])}}]})
    row3 = row2 + 236 + G
    page.add("diccionario", "tableEx", {"Values": [column("dim_indicador", "codigo_kpi", "KPI"), column("dim_indicador", "nombre_indicador", "Indicador"), column("dim_indicador", "formula", "Fórmula"),
                                                   column("dim_indicador", "unidad", "Unidad"), column("dim_indicador", "codigo_fuente", "Fuente")]},
             (X0, row3, 640, BOTTOM - row3), title="Diccionario de indicadores (fórmula, unidad y fuente)", sort={"field": column("dim_indicador", "nombre_indicador")["field"]},
             objects={"values": [{"properties": {"fontSize": lit(9)}}], "columnHeaders": [{"properties": {"fontSize": lit(9), "fontColor": color(C["text2"]), "backColor": color(C["canvas"])}}]})
    textbox(page, "limitaciones", (X0 + 640 + G, row3, CW - 640 - G, BOTTOM - row3), [
        [("Limitaciones", {**STYLE_BODY_BOLD, "fontSize": "12pt", "color": NAVY})],
        [("• KPI-07 por pensión, no por pensionista; pensiones desde 2016.", {**STYLE_BODY, "fontSize": "10pt"})],
        [("• Ruptura del saldo migratorio en 2021.", {**STYLE_BODY, "fontSize": "10pt"})],
        [("• PIB y gasto/PIB recientes provisionales y revisables.", {**STYLE_BODY, "fontSize": "10pt"})],
        [("• Solo España: sin datos por comunidad autónoma.", {**STYLE_BODY, "fontSize": "10pt"})],
        [("• Escenarios demográficos del INE, no fiscales.", {**STYLE_BODY, "fontSize": "10pt"})],
        [("• Las relaciones mostradas son descriptivas, no causales.", {**STYLE_BODY, "fontSize": "10pt"})],
    ], container=frame(C["surface"], C["border"]))
    return page


def page_tooltip():
    page = Page("tooltip", "Tooltip · indicador", tooltip=True)
    page.add("definicion", "multiRowCard", {"Values": [measure(F, "Def · indicador", "Indicador"), measure(F, "Def · fórmula", "Fórmula"), measure(F, "Def · unidad", "Unidad"),
                                                       measure(F, "Def · fuente", "Fuente"), measure(F, "Def · cobertura", "Cobertura observada"), measure(F, "Def · descripción", "Definición")]},
             (8, 8, 304, 224), objects={"dataLabels": [{"properties": {"fontSize": lit(9), "color": color(C["text"])}}], "categoryLabels": [{"properties": {"fontSize": lit(8), "color": color(C["text2"])}}]})
    return page


def build_pages():
    return [page_resumen(), page_demografia(), page_contributivo(), page_financiero(), page_escenarios(), page_metodologia(), page_tooltip()]


def theme():
    return {
        "name": "Pensiones España",
        "dataColors": PALETTE,
        "foreground": C["text"], "foregroundNeutralSecondary": C["text2"], "foregroundNeutralTertiary": C["muted"],
        "background": C["surface"], "backgroundLight": C["canvas"], "backgroundNeutral": C["border"], "tableAccent": C["observed"],
        "good": C["good"], "neutral": C["warning"], "bad": C["bad"], "maximum": C["observed"], "center": "#D6E4F5", "minimum": C["surface"],
        "textClasses": {
            "callout": {"fontSize": 28, "fontFace": FONT_BOLD, "color": NAVY},
            "title": {"fontSize": 12, "fontFace": FONT_BOLD, "color": NAVY},
            "header": {"fontSize": 12, "fontFace": FONT_BOLD, "color": NAVY},
            "label": {"fontSize": 10, "fontFace": FONT, "color": C["text2"]},
            "largeTitle": {"fontSize": 22, "fontFace": FONT_BOLD, "color": NAVY},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": {"solid": {"color": C["surface"]}}, "transparency": 0}],
                "border": [{"show": True, "color": {"solid": {"color": C["border"]}}, "radius": 12}],
                "dropShadow": [{"show": False}],
                "padding": [{"top": 10, "bottom": 10, "left": 14, "right": 14}],
                "visualHeader": [{"show": False}],
                "title": [{"fontSize": 12, "fontFamily": FONT_BOLD, "fontColor": {"solid": {"color": NAVY}}}],
            }},
            "page": {"*": {"background": [{"color": {"solid": {"color": C["canvas"]}}, "transparency": 0}],
                           "outspace": [{"color": {"solid": {"color": C["canvas"]}}, "transparency": 0}]}},
        },
    }


def write_report(pages):
    definition = REPORT / "definition"
    write_json(REPORT / "definition.pbir", {"$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0",
                                            "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    write_json(definition / "version.json", {"$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    theme_file = "TemaPensiones.json"
    write_json(definition / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/{VERSIONS['report']}/schema.json",
        "themeCollection": {"customTheme": {"name": theme_file, "reportVersionAtImport": {"visual": VERSIONS["visual"], "report": VERSIONS["report"], "page": VERSIONS["page"]}, "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": theme_file, "path": theme_file, "type": "CustomTheme"}]}],
    })
    write_json(REPORT / "StaticResources" / "RegisteredResources" / theme_file, theme())
    write_json(definition / "pages" / "pages.json", {"$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
                                                      "pageOrder": [page.name for page in pages], "activePageName": pages[0].name})
    for page in pages:
        folder = definition / "pages" / page.name
        content = {"$schema": f"{SCHEMA}/item/report/definition/page/{VERSIONS['page']}/schema.json", "name": page.name, "displayName": page.display}
        if page.tooltip:
            content.update({"displayOption": "ActualSize", "height": 240, "width": 320, "type": "Tooltip", "visibility": "HiddenInViewMode",
                            "pageBinding": {"name": guid("binding", page.key), "type": "Tooltip"}})
        else:
            content.update({"displayOption": "FitToPage", "height": H, "width": W, "visualInteractions": page.interactions()})
        write_json(folder / "page.json", content)
        for visual in page.visuals:
            write_json(folder / "visuals" / visual["name"] / "visual.json", visual)


def write_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def validate():
    """Valida cada JSON del informe y del proyecto contra el esquema oficial que declara en $schema."""
    import jsonschema
    import requests
    from referencing import Registry, Resource

    cache = {}

    def retrieve(uri):
        if uri not in cache:
            cache[uri] = requests.get(uri, timeout=60).json()
        return Resource.from_contents(cache[uri])

    registry = Registry(retrieve=retrieve)
    checked = 0
    for path in sorted(OUT.rglob("*")):
        if path.suffix not in (".json", ".pbir", ".pbism", ".pbip") or "StaticResources" in path.parts or ".pbi" in path.parts or path.name in ("diagramLayout.json",):
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if "$schema" not in document:
            continue
        schema = retrieve(document["$schema"]).contents
        validator = jsonschema.Draft7Validator(schema, registry=registry)
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        if errors:
            raise ValueError(f"{path.relative_to(OUT)} no cumple {document['$schema']}: " + " | ".join(f"{list(e.path)}: {e.message[:200]}" for e in errors[:5]))
        checked += 1
    check_measure_tables()
    print(f"Validación correcta: {checked} archivos JSON del proyecto cumplen sus esquemas oficiales y todas las medidas se referencian desde su tabla.")


def check_measure_tables():
    """Power BI no encuentra una medida si el visual la busca en otra tabla («Hubo un problema con uno o más campos»)."""
    home = {name: table for table, items in MEASURES.items() for name, *_ in items}
    wrong = set()

    def walk(node, where):
        if isinstance(node, dict):
            if isinstance(node.get("Measure"), dict):
                entity = node["Measure"]["Expression"]["SourceRef"].get("Entity")
                name = node["Measure"]["Property"]
                if home.get(name) != entity:
                    wrong.add(f"{where}: [{name}] referenciada en {entity}, definida en {home.get(name, 'ninguna tabla')}")
            for value in node.values():
                walk(value, where)
        elif isinstance(node, list):
            for value in node:
                walk(value, where)

    for path in REPORT.rglob("visual.json"):
        walk(json.loads(path.read_text(encoding="utf-8")), path.parent.name)
    if wrong:
        raise ValueError("Medidas referenciadas desde una tabla equivocada: " + " | ".join(sorted(wrong)))


def clean():
    """Borra lo generado y conserva lo que crea Power BI Desktop (.platform, .pbi/localSettings.json, diagramLayout.json).
    La caché de datos se elimina porque el modelo cambia: Power BI pedirá «Actualizar»."""
    # OneDrive y Windows bloquean a veces las carpetas un instante: se borran archivos y se reintentan las carpetas.
    locked = []
    for folder in (MODEL / "definition", REPORT / "definition", REPORT / "StaticResources"):
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_file():
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                path.unlink()
        for path in sorted([folder, *[p for p in folder.rglob("*") if p.is_dir()]], key=lambda item: len(item.parts), reverse=True):
            for attempt in range(5):
                try:
                    os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)  # OneDrive marca las carpetas como solo lectura
                    path.rmdir()
                    break
                except FileNotFoundError:
                    break
                except OSError:
                    time.sleep(0.5 * (attempt + 1))
            else:
                locked.append(path)
    (MODEL / ".pbi" / "cache.abf").unlink(missing_ok=True)
    stale = [path for path in locked if "pages" in path.parts and path.name != "pages" and not any(path.iterdir())]
    if stale:
        print(f"Aviso: {len(stale)} carpetas vacías no se pudieron borrar (bloqueo de OneDrive). Bórrelas a mano si Power BI lo pide: {[str(p) for p in stale]}")


def main():
    if not CSV_DIR.is_dir():
        raise SystemExit("No existe data/serving/csv: ejecute antes `python main.py`.")
    clean()
    write_model(column_types())
    pages = build_pages()
    write_report(pages)
    write_json(OUT / f"{NAME}.pbip", {"$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
                                      "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}})
    write_text(OUT / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    measures = sum(len(items) for items in MEASURES.values())
    print(f"Proyecto de Power BI generado en {OUT / (NAME + '.pbip')}: {len(pages)} páginas, {sum(len(p.visuals) for p in pages)} visuales, {measures} medidas")
    if "--validar" in sys.argv:
        validate()


if __name__ == "__main__":
    main()
