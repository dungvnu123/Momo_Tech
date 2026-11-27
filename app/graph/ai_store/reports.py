import hashlib
import json

from app.ai.shield.indicators import canonical_indicator

from ..builder import _Writer
from ..normalize import phone


class ReportStore:
    def persist_report(self, report_id, text, analysis):
        row = self.connection.execute("SELECT payload FROM scam_reports WHERE id=?", (report_id,)).fetchone()
        if row is None:
            raise KeyError(report_id)
        original = json.loads(row[0])
        if original["raw_text"] != text:
            raise ValueError("Analysis text does not match the stored report")
        from app.ai.shield.indicators import validate_report
        validate_report(analysis, text)
        payload = {"report_id": report_id, "input_hash": hashlib.sha256(text.encode()).hexdigest(),
                   **analysis.model_dump()}
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO ai_report_analysis VALUES (?, ?)",
                                    (report_id, json.dumps(payload, ensure_ascii=False)))
            self.connection.execute("DELETE FROM edges WHERE source_table='ai_report_analysis' AND source_id=?", (report_id,))
            writer = _Writer(self)
            seen = set()
            for indicator in analysis.indicators:
                identifier = canonical_indicator(indicator)
                if identifier in seen:
                    continue
                seen.add(identifier)
                kind = {"account": "Account", "phone": "Phone", "domain": "Domain", "url": "Url"}[identifier.split(":", 1)[0]]
                writer.node(identifier, kind)
                writer.edge("report:" + report_id, identifier, "MENTIONS", "ai_report_analysis",
                            report_id, original["reported_at"], suffix=hashlib.sha256(identifier.encode()).hexdigest()[:16],
                            ai_generated=True, verdict=analysis.verdict, confidence=analysis.confidence,
                            reporter_is_victim=analysis.reporter_is_victim)

    def reports_for_indicator(self, identifier, *, limit=20, offset=0):
        page = self.related_edges(identifier, edge_type="MENTIONS", direction="incoming", limit=limit, offset=offset)
        total = self.connection.execute(
            "SELECT COUNT(DISTINCT source) FROM edges WHERE target=? AND kind='MENTIONS'", (identifier,),
        ).fetchone()[0]
        return {**page, "total_reports": total}

    def report_coverage(self):
        total = self.connection.execute("SELECT COUNT(*) FROM scam_reports").fetchone()[0]
        indexed = self.connection.execute("SELECT COUNT(*) FROM ai_report_analysis").fetchone()[0] if self.has_table("ai_report_analysis") else 0
        return {"indexed": indexed, "total": total, "complete": total > 0 and indexed == total}

    def self_reports(self, wallet):
        if not self.has_table("ai_report_analysis"):
            return 0
        return self.connection.execute(
            "SELECT COUNT(*) FROM edges e JOIN ai_report_analysis a ON a.id=e.source_id "
            "WHERE e.target=? AND e.kind='REPORTED_BY' AND json_extract(a.payload, '$.reporter_is_victim')=1",
            (wallet,),
        ).fetchone()[0]

    def reporter_applications(self, report_id):
        row = self.connection.execute("SELECT payload FROM scam_reports WHERE id=?", (report_id,)).fetchone()
        if row is None:
            return []
        reporter = json.loads(row[0]).get("reporter_phone")
        if not reporter:
            return []
        return [item[0] for item in self.connection.execute(
            "SELECT id FROM applications WHERE wallet=? ORDER BY id", (phone(reporter),),
        )]
