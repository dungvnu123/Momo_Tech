import json

from app import db

from ..store import AI_TABLES


class MetadataStore:
    def has_table(self, table):
        return db.has_table(self.connection, table)

    def ai_record(self, table, identifier):
        if table not in AI_TABLES:
            raise ValueError("Unknown AI table")
        if not self.has_table(table):
            return None
        row = self.connection.execute(f"SELECT payload FROM {table} WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None
