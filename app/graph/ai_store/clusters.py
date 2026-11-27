import json


class ClusterStore:
    def persist_cluster(self, summary, decision):
        if summary.cluster_id != decision.cluster_id:
            raise ValueError("Mismatched cluster ID")
        for app_id in summary.app_ids:
            self.application(app_id)
        payload = {"summary": summary.model_dump(), "triage": decision.model_dump()}
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO ai_clusters VALUES (?, ?)",
                                    (summary.cluster_id, json.dumps(payload, ensure_ascii=False)))
