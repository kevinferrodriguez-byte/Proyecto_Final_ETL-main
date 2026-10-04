class IneEndpoints:
    def __init__(self, config):
        self.templates = config["endpoints"]
        self.base_url = config["base_url"].rstrip("/")
        self.language = config["language"]

    def data_table(self, table_id):
        return self.templates["data_table"].format(base_url=self.base_url, language=self.language, table_id=table_id)

    def groups_table(self, table_id):
        return self.templates["groups_table"].format(base_url=self.base_url, language=self.language, table_id=table_id)

    def group_values(self, table_id, group_id):
        return self.templates["group_values"].format(
            base_url=self.base_url,
            language=self.language,
            table_id=table_id,
            group_id=group_id,
        )

    def variable(self, variable_id):
        return self.templates["variable"].format(base_url=self.base_url, language=self.language, variable_id=variable_id)
