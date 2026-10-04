import numpy as np
import pandas as pd


class JsonStatParser:
    """Convierte un conjunto JSON-stat 2.0 (valores dispersos en orden row-major) en una tabla larga.

    Cada observación recibe la etiqueta de cada dimensión y el flag de estado publicado por Eurostat.
    No imputa huecos: una posición sin valor en `value` no genera fila.
    """

    def parse(self, payload):
        ids = payload["id"]
        sizes = payload["size"]
        if len(ids) != len(sizes):
            raise ValueError(f"JSON-stat incoherente: {len(ids)} dimensiones y {len(sizes)} tamaños.")
        codes = [self._codes(payload, dimension, size) for dimension, size in zip(ids, sizes)]
        positions = np.array(sorted(int(position) for position in payload["value"]), dtype="int64")
        total = int(np.prod(sizes))
        if len(positions) and (positions.min() < 0 or positions.max() >= total):
            raise ValueError(f"JSON-stat con posiciones fuera de rango (0–{total - 1}).")
        columns = {}
        remainder = positions.copy()
        for dimension, size, dimension_codes in reversed(list(zip(ids, sizes, codes))):
            columns[dimension] = np.asarray(dimension_codes, dtype=object)[remainder % size]
            remainder //= size
        frame = pd.DataFrame({dimension: columns[dimension] for dimension in ids})
        values = payload["value"]
        status = payload.get("status", {}) or {}
        frame["valor"] = [values[str(position)] if str(position) in values else values.get(position) for position in positions]
        frame["flag"] = [status.get(str(position)) for position in positions]
        return frame

    def _codes(self, payload, dimension, size):
        index = payload["dimension"][dimension]["category"]["index"]
        if isinstance(index, list):
            ordered = list(index)
        else:
            ordered = [code for code, _ in sorted(index.items(), key=lambda item: item[1])]
        if len(ordered) != size:
            raise ValueError(f"La dimensión {dimension} declara tamaño {size} y tiene {len(ordered)} categorías.")
        return ordered
