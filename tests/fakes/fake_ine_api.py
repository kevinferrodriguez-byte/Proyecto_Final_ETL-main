from collections import Counter


class FakeIneApi:
    def __init__(self, catalog):
        self.catalog = catalog
        self.calls = Counter()

    def groups(self, table_id):
        self.calls[("groups", table_id)] += 1
        return self.catalog.groups

    def group_values(self, table_id, group_id):
        self.calls[("group_values", table_id, group_id)] += 1
        return self.catalog.values[group_id]

    def variable(self, variable_id):
        self.calls[("variable", variable_id)] += 1
        return self.catalog.variables[variable_id]
