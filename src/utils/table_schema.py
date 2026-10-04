import pandas as pd


class TableSchema:
    def __init__(self, name, dtypes, nullable, domains):
        self.name = name
        self.dtypes = dtypes
        self.nullable = frozenset(nullable)
        self.domains = {column: frozenset(values) for column, values in domains.items()}

    def columns(self):
        return list(self.dtypes)

    def empty(self):
        return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in self.dtypes.items()})

    def validate(self, frame):
        problems = self.problems(frame)
        if problems:
            raise ValueError(f"El conjunto no cumple el {self.name}: " + "; ".join(problems) + ".")

    def problems(self, frame):
        present = set(frame.columns)
        problems = []
        missing = [name for name in self.dtypes if name not in present]
        unexpected = [name for name in frame.columns if name not in self.dtypes]
        if missing:
            problems.append(f"faltan columnas: {', '.join(missing)}")
        if unexpected:
            problems.append(f"columnas no previstas: {', '.join(map(str, unexpected))}")
        for name, dtype in self.dtypes.items():
            if name in present:
                problems.extend(self._column_problems(frame[name], name, dtype))
        return problems

    def _column_problems(self, column, name, dtype):
        if column.dtype != pd.api.types.pandas_dtype(dtype):
            return [f"la columna {name} tiene tipo {column.dtype}; se esperaba {dtype}"]
        problems = []
        null_count = int(column.isna().sum())
        if null_count and name not in self.nullable:
            problems.append(f"la columna {name} tiene {null_count} valores nulos y no admite nulos")
        domain = self.domains.get(name)
        if domain is not None:
            invalid = sorted(set(column.dropna().unique()) - domain)
            if invalid:
                problems.append(
                    f"la columna {name} tiene valores fuera de dominio: {', '.join(map(str, invalid))} "
                    f"(permitidos: {', '.join(sorted(domain))})"
                )
        return problems
