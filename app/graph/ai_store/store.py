from ..store import GraphStore
from .metadata import MetadataStore
from .reports import ReportStore
from .entities import EntityStore
from .clusters import ClusterStore


class AIStore(GraphStore, MetadataStore, ReportStore, EntityStore, ClusterStore):
    def __init__(self, database, *, read_only=False):
        super().__init__(database, read_only=read_only)
        if not read_only:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS ai_report_analysis (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ai_entity_decisions (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ai_clusters (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ai_entity_members (
                    app_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ai_entity_lookup ON ai_entity_members(entity_id);
            """)
