import json
from pathlib import Path

import pandas as pd

CSV = Path(__file__).resolve().parents[2] / "data" / "serving" / "csv"
SALIDA = Path(__file__).with_name("datos.json")


def leer(nombre):
    return pd.read_csv(CSV / f"{nombre}.csv", encoding="utf-8-sig")


def limpio(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, float):
        return round(valor, 4)
    return valor


panel = leer("dm_panel_anual").sort_values("anyo")
fact = leer("fact_indicadores_anual")
proy = leer("fact_proyecciones_demograficas")
dim_ind = leer("dim_indicador")
dim_esc = leer("dim_escenario")
dim_sexo = leer("dim_sexo")
dim_grupo = leer("dim_grupo_edad")
calidad = leer("aux_calidad_reglas")

codigo = dict(zip(dim_ind.indicador_key, dim_ind.codigo_indicador))
fact["codigo"] = fact.indicador_key.map(codigo)
proy["codigo"] = proy.indicador_key.map(codigo)
sexo = dict(zip(dim_sexo.sexo_key, dim_sexo.codigo_sexo))
grupo = dict(zip(dim_grupo.grupo_edad_key, dim_grupo.codigo_grupo))

# Panel anual: una fila por año (solo datos observados)
columnas = [c for c in panel.columns if c not in ("tiempo_key", "territorio_key", "gold_run_id")]
serie = {c: [limpio(v) for v in panel[c]] for c in columnas}

# Años provisionales por indicador (para marcar puntos huecos)
provisional = (fact[fact.estado_dato == "provisional"].groupby("codigo")["tiempo_key"]
               .apply(lambda s: sorted(int(a) for a in s.unique())).to_dict())

# Esperanza de vida a los 65 por sexo
ev = fact[(fact.codigo == "esperanza_vida_65")].copy()
ev["sexo"] = ev.sexo_key.map(sexo)
ev = ev[ev.grupo_edad_key.map(grupo).isin(["total"]) | ev.grupo_edad_key.isna()]
esperanza65 = {s: {int(a): round(v, 2) for a, v in zip(g.tiempo_key, g.valor)} for s, g in ev.groupby("sexo")}

# Proyecciones: 4 indicadores x 8 escenarios (ambos sexos, grupo total)
ind_esc = ["tasa_dependencia_mayores", "indice_envejecimiento", "porcentaje_mayores_65", "tasa_dependencia"]
p = proy[proy.codigo.isin(ind_esc) & (proy.sexo_key.map(sexo) == "total") & (proy.grupo_edad_key.map(grupo) == "total")]
cod_esc = dict(zip(dim_esc.escenario_key, dim_esc.codigo_escenario))
p = p.assign(escenario=p.escenario_key.map(cod_esc))
proyecciones = {}
for (ind, esc), g in p.groupby(["codigo", "escenario"]):
    g = g.sort_values("tiempo_key")
    proyecciones.setdefault(ind, {})[esc] = {"anyos": [int(a) for a in g.tiempo_key], "valores": [round(v, 3) for v in g.valor]}

escenarios = dim_esc[["codigo_escenario", "escenario_kr", "etiqueta_ine", "es_escenario_principal"]].to_dict("records")

indicadores = dim_ind[["codigo_indicador", "nombre_indicador", "tipo_indicador", "codigo_kpi", "unidad", "formula",
                       "codigo_fuente", "cobertura_desde", "cobertura_hasta", "sentido", "descripcion"]]
indicadores = [{k: limpio(v) for k, v in fila.items()} for fila in indicadores.to_dict("records")]

reglas = [{k: limpio(v) for k, v in fila.items()} for fila in calidad[["capa", "regla", "descripcion", "resultado", "detalle"]].to_dict("records")]

generado = str(fact.fecha_generacion.max())[:16]
datos = {"panel": serie, "provisional": provisional, "esperanza65": esperanza65, "proyecciones": proyecciones,
         "escenarios": escenarios, "indicadores": indicadores, "reglas": reglas, "generado": generado}
SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

print("bytes:", SALIDA.stat().st_size)
print("columnas panel:", columnas)
print("provisional:", provisional)
print("ev65 sexos:", list(esperanza65), "años", min(esperanza65["total"]), max(esperanza65["total"]))
print("proyecciones:", {k: list(v) for k, v in proyecciones.items()})
print("sentidos:", dim_ind.sentido.unique(), "tipos:", dim_ind.tipo_indicador.unique())
print(dim_ind[["codigo_indicador", "codigo_kpi", "nombre_indicador", "unidad", "sentido"]].to_string())
print(calidad.groupby(["capa", "resultado"]).size().unstack(fill_value=0))
print(calidad[calidad.resultado != "cumple"][["capa", "regla", "detalle"]].to_string()[:1500])
print("generado", generado)
