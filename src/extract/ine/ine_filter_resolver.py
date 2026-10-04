class IneFilterResolver:
    def __init__(self, api):
        self.api = api
        self.groups_by_table = {}
        self.values_by_group = {}
        self.variable_names = {}

    def resolve(self, table_id, filters):
        groups = self._groups(table_id)
        tv_filters = []
        for group_name, rules in filters.items():
            group_id = groups.get(group_name)
            if group_id is None:
                raise ValueError(f"El grupo '{group_name}' no existe en la tabla INE {table_id}. Grupos disponibles: {', '.join(groups)}.")
            index = self._values(table_id, group_id)
            tv_filters.extend(self._select(table_id, group_name, index, rules))
        return tv_filters

    def _groups(self, table_id):
        if table_id not in self.groups_by_table:
            self.groups_by_table[table_id] = {group["Nombre"]: group["Id"] for group in self.api.groups(table_id)}
        return self.groups_by_table[table_id]

    def _values(self, table_id, group_id):
        key = (table_id, group_id)
        if key not in self.values_by_group:
            by_name = {}
            by_variable = {}
            for value in self.api.group_values(table_id, group_id):
                by_name.setdefault(value["Nombre"], []).append(value)
                by_variable.setdefault(value["FK_Variable"], []).append(value)
            self.values_by_group[key] = {"by_name": by_name, "by_variable": by_variable}
        return self.values_by_group[key]

    def _select(self, table_id, group_name, index, rules):
        candidates = []
        variable_name = rules.get("include_values_from_variable")
        if variable_name:
            candidates.extend(self._values_of_variable(table_id, group_name, index, variable_name))
        for label in rules.get("values", []) + rules.get("include_labels", []):
            candidates.append(self._value_with_label(table_id, group_name, index, label))

        excluded_labels = frozenset(rules.get("excluded_labels", []))
        selected = {f"{value['FK_Variable']}:{value['Id']}": value["Nombre"] for value in candidates if value["Nombre"] not in excluded_labels}
        expected_count = rules.get("expected_value_count")
        if expected_count is not None and len(selected) != expected_count:
            raise ValueError(f"El filtro '{group_name}' de la tabla INE {table_id} resolvió {len(selected)} valores; se esperaban {expected_count}. Revise los metadatos vigentes y config/config.yaml.")
        return list(selected)

    def _values_of_variable(self, table_id, group_name, index, variable_name):
        values = []
        for variable_id, variable_values in index["by_variable"].items():
            if self._variable_name(variable_id) == variable_name:
                values.extend(variable_values)
        if not values:
            raise ValueError(f"La variable '{variable_name}' no tiene valores en el grupo '{group_name}' de la tabla INE {table_id}.")
        return values

    def _value_with_label(self, table_id, group_name, index, label):
        matches = index["by_name"].get(label)
        if not matches:
            raise ValueError(f"El valor '{label}' no existe en el grupo '{group_name}' de la tabla INE {table_id}. Revise la etiqueta exacta en config/config.yaml.")
        if len(matches) > 1:
            raise ValueError(f"El valor '{label}' es ambiguo en el grupo '{group_name}' de la tabla INE {table_id}: aparece {len(matches)} veces en los metadatos.")
        return matches[0]

    def _variable_name(self, variable_id):
        if variable_id not in self.variable_names:
            self.variable_names[variable_id] = self.api.variable(variable_id)["Nombre"]
        return self.variable_names[variable_id]
