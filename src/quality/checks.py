"""Comprobaciones reutilizables por las reglas de calidad de Oro (modelo y escenarios)."""

import pandas as pd

SAMPLE_SIZE = 5
MAD_SCALE = 0.6745
MEAN_AD_SCALE = 1.253314


def flagged(frame, mask, columns, label):
    mask = mask.fillna(False).astype(bool) if hasattr(mask, "fillna") else mask
    if not mask.any():
        return []
    return [f"{int(mask.sum())} {label}; por ejemplo {frame.loc[mask, columns].head(SAMPLE_SIZE).to_dict('records')}"]


def compare(label, published, expected, epsilon):
    """Compara un valor publicado con su fórmula; tolerancia relativa `epsilon` (mínimo absoluto `epsilon`)."""
    published = published.dropna()
    expected = expected.reindex(published.index)
    tolerance = epsilon * published.abs().clip(lower=1)
    incoherent = (published - expected).abs().gt(tolerance) | expected.isna()
    if not incoherent.any():
        return []
    return [f"{label}: {int(incoherent.sum())} valores no coinciden con sus componentes; por ejemplo {incoherent[incoherent].index[:SAMPLE_SIZE].tolist()}"]


def compare_absolute(label, published, expected, tolerance):
    """Compara con tolerancia absoluta (por ejemplo, personas de redondeo publicadas por la fuente)."""
    published = published.dropna()
    expected = expected.reindex(published.index)
    difference = (published - expected).abs()
    incoherent = difference.gt(tolerance) | expected.isna()
    if not incoherent.any():
        return []
    return [f"{label}: {int(incoherent.sum())} diferencias mayores que {tolerance}; por ejemplo {difference[incoherent].head(SAMPLE_SIZE).to_dict()}"]


def dimension_keys(dimensions, keys):
    problems = []
    for name, (key, code) in keys.items():
        frame = dimensions[name]
        for column in (key, code):
            if frame[column].duplicated().any():
                problems.append(f"{name}: {column} repetido ({sorted(frame.loc[frame[column].duplicated(), column].astype(str).unique())})")
    return problems


def foreign_keys(fact, dimensions, foreign, dimension_keys_by_name, key_columns):
    problems = []
    for column, dimension in foreign.items():
        orphan = ~fact[column].isin(dimensions[dimension][dimension_keys_by_name[dimension][0]])
        problems.extend(flagged(fact, orphan, key_columns, f"filas con {column} inexistente en {dimension}"))
    return problems


def modified_zscore_outliers(series_frame, group_columns, threshold, min_points):
    """Variaciones interanuales atípicas con el z-score modificado (Iglewicz y Hoaglin).

    z(t) = 0,6745 · (d(t) − mediana(d)) / MAD(d), con d(t) = valor(t) − valor(t−1) en años consecutivos.
    Si MAD = 0 se usa la desviación absoluta media. Solo informa: no elimina ni corrige ningún valor.
    """
    findings = []
    evaluated = 0
    for key, series in series_frame.sort_values("anyo").groupby(group_columns):
        years = series["anyo"].to_numpy()
        values = series["valor"].to_numpy()
        consecutive = years[1:] - years[:-1] == 1
        changes = pd.Series(values[1:] - values[:-1], index=years[1:])[consecutive]
        if len(changes) < min_points:
            continue
        median = changes.median()
        deviations = (changes - median).abs()
        mad = deviations.median()
        if mad > 0:
            scores = MAD_SCALE * (changes - median) / mad
        elif deviations.mean() > 0:
            scores = (changes - median) / (MEAN_AD_SCALE * deviations.mean())
        else:
            continue
        evaluated += 1
        labels = key if isinstance(key, tuple) else (key,)
        for year, score in scores[scores.abs().gt(threshold)].items():
            finding = dict(zip(group_columns, labels))
            finding.update({"anyo": int(year), "variacion": round(float(changes[year]), 6), "z_modificado": round(float(score), 3)})
            findings.append(finding)
    return {"series_evaluadas": evaluated, "hallazgos": findings}
