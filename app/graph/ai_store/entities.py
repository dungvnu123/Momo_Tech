import hashlib
import json

from ..builder import _Writer


class EntityStore:
    def persist_entities(self, pairs, decisions):
        pair_map = {pair.pair_id: pair for pair in pairs}
        if len(pair_map) != len(pairs) or {item.pair_id for item in decisions} != set(pair_map) or len(decisions) != len(pairs):
            raise ValueError("Decision IDs must match input pairs")
        with self.connection:
            for decision in decisions:
                pair = pair_map[decision.pair_id]
                for record in (pair.left, pair.right):
                    original = self.application(record.app_id)
                    if any(getattr(record, field) != original.get(field) for field in ("full_name", "dob", "address")):
                        raise ValueError("Entity input does not match the stored application")
                if decision.decision == "same" and pair.left.dob != pair.right.dob:
                    raise ValueError("Cannot merge people with different dates of birth")
                payload = {**decision.model_dump(), "app_ids": [pair.left.app_id, pair.right.app_id]}
                previous = self.ai_record("ai_entity_decisions", pair.pair_id)
                if previous and set(previous["app_ids"]) != set(payload["app_ids"]):
                    raise ValueError("Pair ID already refers to different applications")
                self.connection.execute("INSERT OR REPLACE INTO ai_entity_decisions VALUES (?, ?)",
                                        (pair.pair_id, json.dumps(payload, ensure_ascii=False)))
            self._refresh_entities()

    def _refresh_entities(self):
        decisions = [json.loads(row[0]) for row in self.connection.execute("SELECT payload FROM ai_entity_decisions")]
        parents = {}

        def root(item):
            parents.setdefault(item, item)
            while parents[item] != item:
                item = parents[item]
            return item

        for decision in decisions:
            left, right = decision["app_ids"]
            if decision["decision"] == "same":
                parents[root(left)] = root(right)
        for decision in decisions:
            if decision["decision"] != "same" and root(decision["app_ids"][0]) == root(decision["app_ids"][1]):
                raise ValueError("Entity decisions contain a conflicting identity merge")
        self.connection.execute("DELETE FROM edges WHERE source_table='ai_entity_decisions'")
        self.connection.execute("DELETE FROM nodes WHERE kind='ResolvedPerson'")
        self.connection.execute("DELETE FROM ai_entity_members")
        groups = {}
        for item in parents:
            groups.setdefault(root(item), []).append(item)
        writer = _Writer(self)
        for members in groups.values():
            if len(members) < 2:
                continue
            entity_id = "entity:" + hashlib.sha256("|".join(sorted(members)).encode()).hexdigest()[:20]
            writer.node(entity_id, "ResolvedPerson")
            for app_id in members:
                evidence = next(item for item in decisions if item["decision"] == "same" and app_id in item["app_ids"])
                self.connection.execute("INSERT INTO ai_entity_members VALUES (?, ?)", (app_id, entity_id))
                writer.edge("app:" + app_id, entity_id, "RESOLVED_AS", "ai_entity_decisions", evidence["pair_id"], None,
                            suffix=app_id, ai_generated=True)
        for decision in decisions:
            if decision["decision"] == "same_household":
                left, right = decision["app_ids"]
                writer.edge("app:" + left, "app:" + right, "HOUSEHOLD_CANDIDATE", "ai_entity_decisions",
                            decision["pair_id"], None, ai_generated=True)

    def entity_details(self, identifier):
        node = self.node(identifier)
        if not self.has_table("ai_entity_members"):
            return {"app_ids": [], "decisions": [], "available": False}
        if node["kind"] == "Application":
            app_ids = [identifier.removeprefix("app:")]
        elif node["kind"] == "Person":
            app_ids = [row[0].removeprefix("app:") for row in self.connection.execute(
                "SELECT source FROM edges WHERE target=? AND kind='APPLIED_BY'", (identifier,))]
        elif node["kind"] == "ResolvedPerson":
            app_ids = [row[0] for row in self.connection.execute("SELECT app_id FROM ai_entity_members WHERE entity_id=?", (identifier,))]
        else:
            raise ValueError("Expected an application or person node")
        if app_ids:
            membership = self.connection.execute("SELECT entity_id FROM ai_entity_members WHERE app_id=?", (app_ids[0],)).fetchone()
            if membership:
                app_ids = [row[0] for row in self.connection.execute(
                    "SELECT app_id FROM ai_entity_members WHERE entity_id=? ORDER BY app_id", (membership[0],))]
        wanted = set(app_ids)
        decisions = [json.loads(row[0]) for row in self.connection.execute("SELECT payload FROM ai_entity_decisions")]
        relevant = [item for item in decisions if wanted.intersection(item["app_ids"])]
        return {"app_ids": sorted(app_ids)[:100], "truncated": len(app_ids) > 100 or len(relevant) > 30,
                "decisions": relevant[:30], "available": True}
