"""Se convierten los archivos crudos de Bronce en DataFrames originales para el análisis exploratorio.
"""

from pathlib import Path
import json

import pandas as pd

from src.transform.eurostat.jsonstat_parser import JsonStatParser

# Identificadores de variable del INE (FK_Variable) → nombre de columna en el DataFrame original.
INE_VARIABLES = {
    349: "territorio",
    18: "sexo",
    355: "edad",
    356: "edad",
    357: "edad",
    260: "concepto",
    876: "escenario_o_tipo_saldo",
    3: "tipo_dato",
    141: "nacionalidad",
    431: "pais_nacimiento",
    259: "grupo_indicadores",
    310: "periodicidad",
    452: "orden_nacimiento",
}
INE_AGE_TYPES = {355: "edad simple", 356: "todas las edades", 357: "tramo abierto"}


def ultimo_manifiesto(carpeta):
    """Último manifiesto con estado «completada» de una carpeta de manifiestos de Bronce."""
    carpeta = Path(carpeta)
    manifiestos = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in carpeta.glob("*.manifest.json")]
    completos = [(path, manifest) for path, manifest in manifiestos if manifest.get("status") == "completada"]
    if not completos:
        raise ValueError(f"No hay manifiestos completados en {carpeta}.")
    return max(completos, key=lambda item: item[1]["started_at_utc"])


def ine_a_dataframe(carpeta_manifiestos, manifiesto=None):
    """DataFrame original del INE: una fila por observación de cada archivo del manifiesto."""
    path, manifiesto = (None, manifiesto) if manifiesto else ultimo_manifiesto(carpeta_manifiestos)
    filas = []
    for entrada in manifiesto["payloads"]:
        series = json.loads((Path(carpeta_manifiestos) / entrada["path"]).read_text(encoding="utf-8"))
        for serie in series:
            atributos = {"tabla_id": entrada["table_id"], "consulta": entrada["query"], "COD": serie.get("COD"), "Nombre": serie.get("Nombre"),
                         "FK_Unidad": serie.get("FK_Unidad"), "FK_Escala": serie.get("FK_Escala")}
            for variable in serie.get("MetaData") or []:
                columna = INE_VARIABLES.get(variable["FK_Variable"], f"variable_{variable['FK_Variable']}")
                atributos[columna] = variable["Nombre"]
                if variable["FK_Variable"] in INE_AGE_TYPES:
                    atributos["tipo_variable_edad"] = INE_AGE_TYPES[variable["FK_Variable"]]
            for observacion in serie.get("Data") or []:
                filas.append({**atributos, **observacion})
    frame = pd.DataFrame(filas)
    frame.attrs["run_id"] = manifiesto["run_id"]
    return frame


def _find(grid, etiqueta, max_filas=12):
    for fila in range(min(max_filas, len(grid))):
        for columna in range(grid.shape[1]):
            valor = grid.iat[fila, columna]
            if isinstance(valor, str) and " ".join(valor.split()).upper() == etiqueta.upper():
                return fila, columna
    raise ValueError(f"No se encontró el encabezado «{etiqueta}» en las primeras {max_filas} filas.")


def _limpiar_etiqueta(valor):
    return " ".join(str(valor).split()) if pd.notna(valor) else None


def excel_a_dataframe(ruta, hoja, etiqueta_encabezado, filas_encabezado=1):
    """DataFrame original de una hoja Excel: todo lo que hay debajo del encabezado, con los tipos que infiere pandas.

    Con `filas_encabezado=2` el nombre de cada columna une la fila superior (rellenada hacia la derecha, como las
    celdas combinadas) y la inferior: «REGIMEN GENERAL | Régimen General (1)».
    """
    grid = pd.read_excel(ruta, sheet_name=hoja, header=None)
    fila, columna_etiqueta = _find(grid, etiqueta_encabezado)
    inferior = [_limpiar_etiqueta(valor) for valor in grid.iloc[fila]]
    if filas_encabezado == 2:
        superior = pd.Series([_limpiar_etiqueta(valor) for valor in grid.iloc[fila - 1]]).ffill().tolist()
        nombres = []
        for posicion, (sup, inf) in enumerate(zip(superior, inferior)):
            if posicion == columna_etiqueta or not sup:
                nombres.append(inf)
            elif inf and inf != sup:
                nombres.append(f"{sup} | {inf}")
            else:
                nombres.append(sup)
    else:
        nombres = inferior
    nombres = [nombre or f"columna_{posicion}" for posicion, nombre in enumerate(nombres)]
    nombres = [nombre if nombres.count(nombre) == 1 else f"{nombre} ({posicion})" for posicion, nombre in enumerate(nombres)]
    datos = pd.read_excel(ruta, sheet_name=hoja, header=None, skiprows=fila + 1)
    datos.columns = nombres[: datos.shape[1]]
    return datos


def seguridad_social_a_dataframes(carpeta_manifiestos, config_fuente, manifiesto=None):
    """DataFrames originales de la Seguridad Social: afiliados (una hoja) y pensiones (número e importe, con columna `hoja`)."""
    path, manifiesto = (None, manifiesto) if manifiesto else ultimo_manifiesto(carpeta_manifiestos)
    rutas = {entrada["file_id"]: Path(carpeta_manifiestos) / entrada["path"] for entrada in manifiesto["payloads"]}
    archivos = config_fuente["files"]
    afiliados = excel_a_dataframe(rutas["afiliados_alta"], archivos["afiliados_alta"]["sheet"], "Periodo", filas_encabezado=2)
    hojas = [archivos["pensionistas_nomina"]["sheet"], *archivos["pensionistas_nomina"].get("additional_sheets", [])]
    pensiones = pd.concat(
        [excel_a_dataframe(rutas["pensionistas_nomina"], hoja, "PERIODO").rename(columns={"columna_1": "MES"}).assign(hoja=hoja) for hoja in hojas],
        ignore_index=True,
    )
    for frame in (afiliados, pensiones):
        frame.attrs["run_id"] = manifiesto["run_id"]
    return {"afiliados": afiliados, "pensiones": pensiones}


def eurostat_a_dataframe(carpeta_manifiestos, manifiesto=None):
    """DataFrame original de Eurostat: una fila por observación de los conjuntos descargados (JSON-stat decodificado)."""
    path, manifiesto = (None, manifiesto) if manifiesto else ultimo_manifiesto(carpeta_manifiestos)
    partes = []
    parser = JsonStatParser()
    for entrada in manifiesto["payloads"]:
        payload = json.loads((Path(carpeta_manifiestos) / entrada["path"]).read_text(encoding="utf-8"))
        partes.append(parser.parse(payload).assign(dataset_id=entrada["dataset_id"], codigo_eurostat=entrada.get("code"), version_fuente=payload.get("updated")))
    frame = pd.concat(partes, ignore_index=True)
    primeras = ["dataset_id", "codigo_eurostat"]
    frame = frame[primeras + [columna for columna in frame.columns if columna not in primeras]]
    frame.attrs["run_id"] = manifiesto["run_id"]
    return frame
