import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.graph import GraphStore, build_graph
from app.graph.normalize import account, phone


class GraphTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "graph.db"
        self.applications = [
            {"app_id": identifier, "phone": wallet, "device_id": device,
             "applied_at": "2026-11-01T08:00:00", "disbursed_at": "2026-11-01T08:10:00",
             "amount": "1000000", "cccd": f"00000000000{index}",
             "ref1_phone": "0911111111", "ref1_relation": "family",
             "ref2_phone": "0911111111", "ref2_relation": "colleague",
             "ip_type": "mobile", "ip": "100.1.2.3", "sim_age_days": "100",
             "address": "Shared dormitory"}
            for index, (identifier, wallet, device) in enumerate([
                ("A", "0900000001", "shared"), ("B", "0900000002", "shared"),
                ("C", "0900000003", "separate"),
            ])
        ]
        self.transfers = [
            {"transfer_id": identifier, "from_wallet": "0900000001", "created_at": timestamp,
             "to_type": "bank", "to_bank": bank, "to_id": "0012345", "amount": "300000",
             "to_name": "Recipient", "note": "Transfer"}
            for identifier, timestamp, bank in [
                ("T1", "2026-11-01T08:20:00", "ACB"),
                ("T2", "2026-11-01T08:30:00", "ACB"),
                ("T3", "2026-11-01T08:40:00", "TCB"),
            ]
        ]
        self.reports = [{"report_id": "R1", "reported_at": "2026-11-02T08:00:00",
                         "reporter_phone": "+84 900 000 001", "raw_text": "Caller says I must pay a fee"}]

    def write_csvs(self):
        for name, rows in [("applications", self.applications),
                           ("wallet_transfers", self.transfers), ("scam_reports", self.reports)]:
            with (self.directory / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

    def build(self, **kwargs):
        self.write_csvs()
        return build_graph(self.directory, self.database, **kwargs)

    def test_shared_device_is_traversable_in_both_directions(self):
        self.build()
        with GraphStore(self.database) as store:
            graph = store.neighborhood("app:A", depth=2)
            self.assertIn("app:B", graph)
            self.assertTrue(graph.has_edge("app:A", "device:shared"))
            self.assertTrue(graph.has_edge("app:B", "device:shared"))
            self.assertFalse(graph.has_edge("device:shared", "app:A"))

    def test_repeated_transfers_and_reference_positions_keep_separate_evidence(self):
        self.build()
        with GraphStore(self.database) as store:
            graph = store.neighborhood("app:A", depth=1)
            self.assertEqual(len(graph["app:A"]["account:bank:ACB:0012345"]), 2)
            self.assertEqual(len(graph["app:A"]["phone:0911111111"]), 2)
            edge_id = "wallet_transfers:T1:SENT_TO"
            edge = graph["app:A"]["account:bank:ACB:0012345"][edge_id]
            self.assertEqual(edge["minutes_after_disbursal"], 10)
            self.assertEqual(edge["pct_of_loan"], 30)
            self.assertEqual(store.source_record(edge_id)["record"]["transfer_id"], "T1")
            self.assertIn("account:bank:TCB:0012345", graph)

    def test_mobile_ip_and_address_do_not_create_shared_nodes(self):
        self.applications[2]["ref1_phone"] = "0922222222"
        self.applications[2]["ref2_phone"] = "0933333333"
        self.build()
        with GraphStore(self.database) as store:
            graph = store.neighborhood("app:A", depth=2)
            self.assertNotIn("app:C", graph)
            self.assertNotIn("IpBlock", store.stats()["node_kinds"])
            self.assertNotIn("Address", store.stats()["node_kinds"])

    def test_vpn_and_new_sim_generate_qualified_links(self):
        self.applications[0].update(ip_type="vpn", ip="185.1.2.45", sim_age_days="5")
        self.build()
        with GraphStore(self.database) as store:
            graph = store.neighborhood("app:A")
            self.assertIn("ipblock:185.1.2.0/24", graph)
            self.assertIn("simblock:09000000", graph)

    def test_latest_wallet_fields_connect_receiving_wallet_to_opening_device(self):
        self.transfers = [{
            **self.transfers[0], "to_type": "momo_wallet", "to_bank": "MoMo", "to_id": "+84 988 888 888",
            "to_wallet_opened_device": "farm-device", "to_wallet_age_days": "2",
            "recipient_in_contacts": "True", "contact_saved_minutes_ago": "5",
            "prior_transfers_to_recipient": "0", "simo_flag": "False", "to_is_merchant": "False",
        }]
        self.build()
        with GraphStore(self.database) as store:
            graph = store.neighborhood("app:A", depth=2)
            self.assertTrue(graph.has_edge("account:momo:0988888888", "device:farm-device"))
            edge = graph["app:A"]["account:momo:0988888888"]["wallet_transfers:T1:SENT_TO"]
            self.assertEqual(edge["contact_saved_minutes_ago"], 5)
            self.assertFalse(edge["simo_flag"])

    def test_report_is_linked_to_reporter_without_extracting_or_inventing_mentions(self):
        self.build()
        with GraphStore(self.database) as store:
            graph = store.neighborhood("report:R1")
            self.assertTrue(graph.has_edge("report:R1", "account:momo:0900000001"))
            self.assertEqual(store.source_record("scam_reports:R1:REPORTED_BY")["record"]["raw_text"],
                             self.reports[0]["raw_text"])
            self.assertNotIn("MENTIONS", store.stats()["edge_kinds"])

    def test_ground_truth_file_is_never_read(self):
        (self.directory / "ground_truth.json").write_text("not even valid json", encoding="utf-8")
        self.assertEqual(self.build()["applications"], 3)

    def test_inconsistent_recipient_is_quarantined_without_false_shared_identity(self):
        self.transfers[0].update(to_type="momo_wallet", to_id="123456789012", to_bank="MoMo")
        self.transfers[1].update(to_type="momo_wallet", to_id="123456789012", to_bank="MoMo")
        self.assertEqual(self.build()["quality_issues"], 2)
        with GraphStore(self.database) as store:
            graph = store.neighborhood("app:A")
            self.assertIn("unresolved:T1", graph)
            self.assertIn("unresolved:T2", graph)
            self.assertEqual(graph.nodes["unresolved:T1"]["kind"], "UnresolvedAccount")
            self.assertFalse(graph["app:A"]["unresolved:T1"]["wallet_transfers:T1:SENT_TO"]["recipient_resolved"])
            self.assertEqual(store.source_record("wallet_transfers:T1:SENT_TO")["record"]["to_id"], "123456789012")

    def test_rebuild_requires_explicit_replace_and_has_stable_counts(self):
        first = self.build()
        with self.assertRaises(FileExistsError):
            build_graph(self.directory, self.database)
        self.assertEqual(first, self.build(replace=True))

    def test_failed_rebuild_rolls_back_to_previous_graph(self):
        first = self.build()
        self.transfers[0]["from_wallet"] = "0999999999"
        with self.assertRaises(ValueError):
            self.build(replace=True)
        with GraphStore(self.database) as store:
            self.assertEqual(store.stats(), first)
            self.assertEqual(store.source_record("wallet_transfers:T1:SENT_TO")["record"]["from_wallet"],
                             "0900000001")

    def test_duplicate_source_id_is_rejected_atomically(self):
        self.applications[1]["app_id"] = "A"
        with self.assertRaises(sqlite3.IntegrityError):
            self.build()
        with GraphStore(self.database) as store:
            self.assertEqual(store.stats()["nodes"], 0)
            self.assertEqual(store.stats()["applications"], 0)

    def test_negative_transfer_timing_is_rejected(self):
        self.transfers[0]["created_at"] = "2026-11-01T08:00:00"
        with self.assertRaises(ValueError):
            self.build()

    def test_limits_mark_result_as_truncated(self):
        self.build()
        with GraphStore(self.database) as store:
            graph = store.neighborhood("app:A", depth=2, max_nodes=3, max_edges=2)
            self.assertLessEqual(len(graph), 3)
            self.assertLessEqual(graph.number_of_edges(), 2)
            self.assertTrue(graph.graph["truncated"])
            with self.assertRaises(KeyError):
                store.neighborhood("app:missing")

    def test_account_identifiers_preserve_leading_zeros_and_bank_namespace(self):
        self.assertEqual(phone("+84 900 000 001"), "0900000001")
        self.assertNotEqual(account("bank", "ACB", "0012345"), account("bank", "TCB", "0012345"))
        self.assertEqual(account("bank", "acb", "00 12345"), "account:bank:ACB:0012345")
        with self.assertRaises(ValueError):
            account("bank", "ACB", "00x12345")


if __name__ == "__main__":
    unittest.main()
