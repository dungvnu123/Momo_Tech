import json

from ..store import AI_TABLES


class MetadataStore:
    def has_table(self, table):
        return bool(self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,),
        ).fetchone())

    def ai_record(self, table, identifier):
        if table not in AI_TABLES:
            raise ValueError("Unknown AI table")
        if not self.has_table(table):
            return None
        row = self.connection.execute(f"SELECT payload FROM {table} WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None
