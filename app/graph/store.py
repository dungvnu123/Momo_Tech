import json
from pathlib import Path

import networkx as nx

from app import db

TABLES = ("applications", "wallet_transfers", "scam_reports")
AI_TABLES = ("ai_report_analysis", "ai_entity_decisions", "ai_clusters")


class GraphStore:
    def __init__(self, database: str | Path, *, read_only: bool = False) -> None:
        self.connection = db.connect(database, read_only=read_only)   # chỉ đọc + chưa có → FileNotFoundError như cũ
        if read_only:
            return
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY, wallet TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS application_wallet ON applications(wallet);
            CREATE TABLE IF NOT EXISTS wallet_transfers (
                id TEXT PRIMARY KEY, wallet TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS transfer_wallet ON wallet_transfers(wallet);
            CREATE TABLE IF NOT EXISTS scam_reports (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL REFERENCES nodes(id),
                target TEXT NOT NULL REFERENCES nodes(id),
                kind TEXT NOT NULL,
                source_table TEXT NOT NULL,
                source_id TEXT NOT NULL,
                observed_at TEXT,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS edge_source ON edges(source);
            CREATE INDEX IF NOT EXISTS edge_target ON edges(target);
            CREATE TABLE IF NOT EXISTS quality_issues (
                source_id TEXT PRIMARY KEY, reason TEXT NOT NULL
            );
        """)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def records(self, table: str):
        if table not in TABLES:
            raise ValueError("Unknown source table")
        for row in self.connection.execute(f"SELECT payload FROM {table} ORDER BY id"):
            yield json.loads(row["payload"])

    def application(self, app_id: str) -> dict:
        row = self.connection.execute(
            "SELECT payload FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        if row is None:
            raise KeyError(app_id)
        return json.loads(row["payload"])

    def node(self, node_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            raise KeyError(node_id)
        return {"id": row["id"], "kind": row["kind"], "attributes": json.loads(row["payload"])}

    def latest_application_loan(self, app_id):
        result = {**self.application(app_id),"loan_id":None}
        if db.has_table(self.connection,"live_loans"):
            row = self.connection.execute("SELECT payload FROM live_loans WHERE payload::jsonb->>'app_id'=? "
                "ORDER BY payload::jsonb->>'disbursed_at' DESC,substring(id from 3)::bigint DESC LIMIT 1",(app_id,)).fetchone()
            if row:
                loan=json.loads(row[0])
                result.update(amount=loan["amount"],disbursed_at=loan["disbursed_at"],loan_id=loan["loan_id"])
        return result

    def edge(self, edge_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
        if row is None:
            raise KeyError(edge_id)
        return self._edge_data(row)

    @staticmethod
    def _edge_data(row) -> dict:
        result = dict(row)
        result["attributes"] = json.loads(result.pop("payload"))
        return result

    def related_edges(
        self, node_id: str, *, edge_type: str | None = None, direction: str = "both",
        limit: int = 50, offset: int = 0,
    ) -> dict:
        if type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or offset < 0:
            raise ValueError("Invalid page bounds")
        clauses = {"incoming": "target = ?", "outgoing": "source = ?",
                   "both": "(source = ? OR target = ?)"}
        if direction not in clauses:
            raise ValueError("Invalid direction")
        self.node(node_id)
        where = clauses[direction]
        parameters = [node_id, node_id] if direction == "both" else [node_id]
        if edge_type is not None:
            where += " AND kind = ?"
            parameters.append(edge_type)
        rows = self.connection.execute(
            f"SELECT * FROM edges WHERE {where} ORDER BY id LIMIT ? OFFSET ?",
            (*parameters, limit + 1, offset),
        ).fetchall()
        return {"edges": [self._edge_data(row) for row in rows[:limit]],
                "truncated": len(rows) > limit,
                "next_offset": offset + limit if len(rows) > limit else None}

    def money_summary(self, app_id: str) -> dict:
        self.application(app_id)
        row = self.connection.execute(
            "SELECT COUNT(*) AS total_transfers, "
            "COALESCE(SUM((payload::jsonb->>'amount')::numeric), 0)::bigint AS total_amount "
            "FROM edges WHERE source = ? AND kind = 'SENT_TO'", ("app:" + app_id,),
        ).fetchone()
        return dict(row)

    def application_transfers(self, app_id: str):
        for row in self.connection.execute(
            "SELECT * FROM edges WHERE source = ? AND kind = 'SENT_TO' ORDER BY id", ("app:" + app_id,),
        ):
            yield self._edge_data(row)

    def source_record(self, edge_id: str) -> dict:
        edge = self.connection.execute(
            "SELECT source_table, source_id FROM edges WHERE id = ?", (edge_id,)
        ).fetchone()
        if edge is None:
            raise KeyError(edge_id)
        table = edge["source_table"]
        if table not in (*TABLES, *AI_TABLES, "live_loans"):
            raise ValueError("Unknown source table")
        row = self.connection.execute(
            f"SELECT payload FROM {table} WHERE id = ?", (edge["source_id"],)
        ).fetchone()
        if row is None:
            raise KeyError(edge["source_id"])
        return {"table": table, "record": json.loads(row["payload"])}

    def stats(self) -> dict:
        result = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (*TABLES, "nodes", "edges", "quality_issues")
        }
        result["node_kinds"] = dict(self.connection.execute(
            "SELECT kind, COUNT(*) FROM nodes GROUP BY kind"
        ))
        result["edge_kinds"] = dict(self.connection.execute(
            "SELECT kind, COUNT(*) FROM edges GROUP BY kind"
        ))
        return result

    def neighborhood(
        self, node_id: str, *, depth: int = 1, max_nodes: int = 200, max_edges: int = 500,
    ) -> nx.MultiDiGraph:
        if not 0 <= depth <= 5 or max_nodes < 1 or max_edges < 1:
            raise ValueError("depth must be 0..5 and graph limits must be positive")
        graph = nx.MultiDiGraph(root=node_id, truncated=False)

        def add_node(identifier):
            node = self.connection.execute("SELECT * FROM nodes WHERE id = ?", (identifier,)).fetchone()
            if node is None:
                raise KeyError(identifier)
            graph.add_node(identifier, kind=node["kind"], **json.loads(node["payload"]))

        add_node(node_id)
        frontier = {node_id}
        expanded = set()
        for _ in range(depth):
            following = set()
            for current in sorted(frontier - expanded):
                expanded.add(current)
                cursor = self.connection.execute(
                    "SELECT * FROM edges WHERE source = ? OR target = ? ORDER BY id LIMIT ?",
                    (current, current, max_edges + 1),
                )
                for edge in cursor:
                    if graph.has_edge(edge["source"], edge["target"], edge["id"]):
                        continue
                    missing = {edge["source"], edge["target"]} - graph.nodes
                    if len(graph) + len(missing) > max_nodes or graph.number_of_edges() >= max_edges:
                        graph.graph["truncated"] = True
                        continue
                    for identifier in sorted(missing):
                        add_node(identifier)
                        following.add(identifier)
                    graph.add_edge(
                        edge["source"], edge["target"], key=edge["id"],
                        kind=edge["kind"], source_table=edge["source_table"],
                        source_id=edge["source_id"], observed_at=edge["observed_at"],
                        **json.loads(edge["payload"]),
                    )
            frontier = following
        return graph
