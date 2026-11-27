import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.graph import GraphStore, build_graph
from app.tools import GraphTools


class GraphToolTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "graph.db"
        applications = [
            {"app_id": identifier, "full_name": "Nguyễn Văn An", "phone": wallet,
             "cccd": "012345678901", "device_id": "shared", "address": "Private address",
             "dob": "1990-01-01", "ref1_phone": "0987654321", "ref1_name": "Private name",
             "applied_at": "2026-11-01T08:00:00", "disbursed_at": "2026-11-01T08:10:00",
             "amount": "1000000", "is_emulator": "False"}
            for identifier, wallet in [("A", "0900000001"), ("B", "0900000002")]
        ]
        transfers = [
            {"transfer_id": identifier, "from_wallet": "0900000001",
             "created_at": "2026-11-01T08:20:00", "to_type": "bank", "to_bank": "ACB",
             "to_id": "001234567890", "amount": "300000", "to_name": recipient,
             "note": "Call 0987654321; private name and address"}
            for identifier, recipient in [("T1", "NGUYEN VAN AN"), ("T2", "Different Person")]
        ]
        reports = [{"report_id": "R1", "reported_at": "2026-11-02T08:00:00",
                    "reporter_phone": "0900000001", "raw_text": "Contact 0987654321 at Private address"}]
        for table, rows in [("applications", applications), ("wallet_transfers", transfers),
                            ("scam_reports", reports)]:
            with (self.directory / f"{table}.csv").open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
        build_graph(self.directory, self.database)
        self.tools = GraphTools(self.database)

    def test_application_masks_personal_fields_and_omits_names_address_dob(self):
        response = self.tools.get_application("app:A")
        self.assertTrue(response["ok"])
        record = response["data"]["application"]
        self.assertEqual(record["cccd"], "0123****8901")
        self.assertEqual(record["phone"], "090****001")
        for key in ("full_name", "address", "dob", "ref1_name", "device_id"):
            self.assertNotIn(key, record)
        self.assertTrue(record["device_node_id"].startswith("node:"))

    def test_follow_returned_alias_to_shared_device_and_other_application(self):
        first = self.tools.neighbors("app:A", edge_type="USES_DEVICE", direction="outgoing")
        alias = first["data"]["edges"][0]["target"]
        second = self.tools.neighbors(alias, edge_type="USES_DEVICE", direction="incoming")
        self.assertTrue(second["ok"])
        self.assertEqual({edge["source"] for edge in second["data"]["edges"]}, {"app:A", "app:B"})
        application_alias = self.tools.get_application("A")["data"]["application"]["device_node_id"]
        self.assertEqual(alias, application_alias)

    def test_pagination_is_stable_and_keeps_parallel_edges(self):
        first = self.tools.neighbors("app:A", edge_type="SENT_TO", limit=1)
        self.assertTrue(first["data"]["truncated"])
        self.assertEqual(first["data"]["next_offset"], 1)
        second = self.tools.neighbors("app:A", edge_type="SENT_TO", limit=1, offset=1)
        self.assertFalse(second["data"]["truncated"])
        self.assertIsNone(second["data"]["next_offset"])
        self.assertNotEqual(first["data"]["edges"][0]["edge_id"], second["data"]["edges"][0]["edge_id"])
        self.assertEqual(first["data"]["edges"][0]["target"], second["data"]["edges"][0]["target"])

    def test_money_flow_totals_cover_all_pages_and_do_not_disclose_recipient_names(self):
        first = self.tools.money_flow("A", limit=1)
        self.assertTrue(first["ok"])
        self.assertEqual(first["data"]["total_transfers"], 2)
        self.assertEqual(first["data"]["total_amount"], 600000)
        self.assertEqual(first["data"]["returned_count"], 1)
        self.assertTrue(first["data"]["transfers"][0]["attributes"]["recipient_name_matches_applicant"])
        second = self.tools.money_flow("A", offset=1)
        self.assertFalse(second["data"]["transfers"][0]["attributes"]["recipient_name_matches_applicant"])
        self.assertNotIn("NGUYEN VAN AN", json.dumps(first))

    def test_application_with_no_transfers_is_valid_empty_result(self):
        response = self.tools.money_flow("B")
        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["transfers"], [])
        self.assertEqual(response["data"]["total_amount"], 0)

    def test_evidence_returns_real_source_id_but_masks_source_data(self):
        response = self.tools.get_evidence("wallet_transfers:T1:SENT_TO")
        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["record"]["transfer_id"], "T1")
        self.assertEqual(response["data"]["record"]["to_id"], "0012****7890")
        self.assertNotIn("note", response["data"]["record"])
        self.assertNotIn("to_name", response["data"]["record"])

    def test_report_evidence_omits_unredacted_free_text(self):
        response = self.tools.get_evidence("scam_reports:R1:REPORTED_BY")
        self.assertTrue(response["ok"])
        self.assertTrue(response["data"]["record"]["raw_text_omitted"])
        self.assertNotIn("raw_text", response["data"]["record"])

    def test_no_raw_pii_in_nested_ids_or_edge_attributes(self):
        responses = [self.tools.get_application("A"), self.tools.neighbors("app:A"),
                     self.tools.money_flow("A"), self.tools.get_evidence("applications:A:REFERENCE:ref1"),
                     self.tools.get_evidence("wallet_transfers:T1:SENT_TO")]
        text = json.dumps(responses, ensure_ascii=False)
        for private in ("0900000001", "0987654321", "012345678901", "001234567890",
                        "Nguyễn Văn An", "Private address", "device:shared", "person:"):
            self.assertNotIn(private, text)

    def test_invalid_limits_and_filters_fail_before_query(self):
        for arguments in ({"limit": 51}, {"limit": True}, {"limit": 0}, {"offset": -1},
                          {"edge_type": "DROP TABLE nodes"}, {"direction": "invalid"}, {"depth": 3}):
            with self.subTest(arguments=arguments):
                response = self.tools.call("neighbors", {"node_id": "app:A", **arguments})
                self.assertEqual(response["error"]["code"], "invalid_arguments")
        self.assertEqual(self.tools.get_application(" ")["error"]["code"], "invalid_arguments")

    def test_missing_objects_and_unknown_tools_return_safe_errors(self):
        for response in (self.tools.get_application("missing"), self.tools.neighbors("app:missing"),
                         self.tools.neighbors("node:unknown"), self.tools.get_evidence("fake")):
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "not_found")
        self.assertEqual(self.tools.call("execute_sql", {})["error"]["code"], "unknown_tool")

    def test_sql_in_id_cannot_execute(self):
        response = self.tools.get_application("A'; DROP TABLE applications; --")
        self.assertEqual(response["error"]["code"], "not_found")
        self.assertTrue(self.tools.get_application("A")["ok"])

    def test_missing_database_is_not_created(self):
        path = self.directory / "missing.db"
        response = GraphTools(path).get_application("A")
        self.assertEqual(response["error"]["code"], "storage_unavailable")
        self.assertFalse(path.exists())

    def test_store_read_only_connection_rejects_writes(self):
        with GraphStore(self.database, read_only=True) as store:
            with self.assertRaises(sqlite3.OperationalError):
                store.connection.execute("DELETE FROM nodes")

    def test_aliases_are_scoped_to_a_tool_instance(self):
        alias = self.tools.get_application("A")["data"]["application"]["device_node_id"]
        response = GraphTools(self.database).neighbors(alias)
        self.assertEqual(response["error"]["code"], "not_found")

    def test_definitions_expose_validated_tools_without_handlers(self):
        definitions = self.tools.definitions
        self.assertEqual({item["name"] for item in definitions},
                         {"get_application", "neighbors", "money_flow", "get_evidence", "get_cluster",
                          "account_senders", "reports_mentioning", "timeline", "tech_profile", "entity_info", "cluster_money_flow"})
        for definition in definitions:
            self.assertFalse(definition["parameters"]["additionalProperties"])
            self.assertNotIn("handler", definition)
        neighbors = next(item for item in definitions if item["name"] == "neighbors")
        self.assertEqual(neighbors["parameters"]["properties"]["limit"]["maximum"], 50)


if __name__ == "__main__":
    unittest.main()
