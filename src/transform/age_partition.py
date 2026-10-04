import pandas as pd

GROUP_KEYS = ["tabla_id", "metrica", "fecha_referencia", "sexo", "escenario"]


class AgePartition:
    def __init__(self, top_age):
        self.top_age = top_age

    def apply(self, frame):
        age_tables = frame.loc[frame["tipo_edad"].ne("total"), "tabla_id"].unique()
        aged = frame["tabla_id"].isin(age_tables)
        partitioned = self._partition(frame[aged].reset_index(drop=True))
        result = pd.concat([frame[~aged], partitioned["frame"]], ignore_index=True)
        return {"frame": result.astype(frame.dtypes.to_dict()), "homologation": partitioned["homologation"]}

    def _partition(self, frame):
        simple = frame["tipo_edad"].eq("simple")
        open_interval = frame["tipo_edad"].eq("tramo_abierto")
        with_value = frame["valor"].notna()
        groups = frame[GROUP_KEYS]
        available = simple & with_value

        last_age = self._by_group(frame["edad_min"].where(available), groups, "max")
        first_age = self._by_group(frame["edad_min"].where(available), groups, "min")
        simple_count = self._by_group(available.astype("int64"), groups, "sum")
        if last_age.isna().any():
            raise ValueError(self._describe(frame, last_age.isna(), "sin edades simples con dato"))
        gaps = first_age.ne(0) | simple_count.ne(last_age + 1)
        if gaps.any():
            raise ValueError(self._describe(frame, gaps, "sin edades simples contiguas desde 0"))

        current_start = (last_age + 1).astype("int64")
        homologated_start = current_start.clip(upper=self.top_age)
        current = open_interval & frame["edad_min"].eq(current_start)
        published = open_interval & frame["edad_min"].eq(homologated_start)
        for mask, description in ((current, "tramo abierto vigente"), (published, "tramo abierto homologado")):
            count = self._by_group(mask.astype("int64"), groups, "sum")
            if count.ne(1).any():
                raise ValueError(self._describe(frame, count.ne(1), f"sin exactamente un {description}"))

        detail = (available & frame["edad_min"].lt(homologated_start)) | published
        homologation = self._homologation(frame, groups, available, current, published, current_start, homologated_start)
        result = frame[with_value | ~simple].copy()
        result["es_control"] = ~detail[with_value | ~simple]
        return {"frame": result, "homologation": homologation}

    def _homologation(self, frame, groups, available, current, published, current_start, homologated_start):
        swapped = current_start.gt(homologated_start)
        components = (available & frame["edad_min"].ge(homologated_start)) | current
        values = pd.DataFrame(
            {
                "components": frame["valor"].where(components & swapped, 0.0),
                "published": frame["valor"].where(published & swapped, 0.0),
            }
        )
        summary = values.groupby([groups[key] for key in GROUP_KEYS], dropna=False).sum()
        affected = swapped.groupby([groups[key] for key in GROUP_KEYS], dropna=False).any()
        return summary[affected].reset_index()

    def _by_group(self, values, groups, function):
        return values.groupby([groups[key] for key in GROUP_KEYS], dropna=False).transform(function)

    def _describe(self, frame, mask, problem):
        affected = frame.loc[mask, GROUP_KEYS].drop_duplicates()
        return f"La partición de edades falla en {len(affected)} grupos: {problem}; por ejemplo {affected.head(3).to_dict('records')}."
