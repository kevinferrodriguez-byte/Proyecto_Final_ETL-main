class QualityEvaluation:
    def __init__(self):
        self.rules = []
        self.metrics = {}

    def check(self, name, description, problems):
        self.rules.append(
            {
                "regla": name,
                "descripcion": description,
                "resultado": "falla" if problems else "cumple",
                "detalle": list(problems),
            }
        )
        return not problems

    def warn(self, name, description, findings):
        self.rules.append(
            {
                "regla": name,
                "descripcion": description,
                "resultado": "advertencia" if findings else "cumple",
                "detalle": list(findings),
            }
        )

    def skip(self, name, description, reason):
        self.rules.append({"regla": name, "descripcion": description, "resultado": "no_evaluada", "detalle": [reason]})

    def summary(self):
        results = [rule["resultado"] for rule in self.rules]
        return {
            "aprobadas": results.count("cumple"),
            "advertencias": results.count("advertencia"),
            "fallas": results.count("falla"),
            "no_evaluadas": results.count("no_evaluada"),
        }

    def passed(self):
        return all(rule["resultado"] != "falla" for rule in self.rules)

    def problems(self):
        return [problem for rule in self.rules if rule["resultado"] == "falla" for problem in rule["detalle"]]

    def rejection(self, layer):
        return f"{layer} no supera las validaciones de calidad: " + " | ".join(self.problems())

    def null_fractions(self, frame, max_fraction, structural_columns):
        fractions = frame.isna().mean().round(6).to_dict()
        self.metrics["fraccion_nulos_por_columna"] = {column: float(value) for column, value in fractions.items()}
        self.metrics["columnas_con_nulos_estructurales"] = sorted(structural_columns)
        exceeded = {
            column: value
            for column, value in fractions.items()
            if value > max_fraction and column not in structural_columns
        }
        return [
            f"la columna {column} tiene una fracción de nulos de {value} (máximo quality.max_null_percentage = {max_fraction})"
            for column, value in exceeded.items()
        ]
