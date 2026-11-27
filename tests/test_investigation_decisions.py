import json
import sqlite3
import unittest
from pydantic import ValidationError

import test_backend_integration as fixtures
from app.agents.investigation.schemas import CaseSubmission, ToolStep, submit_definition
from app.services.gemini_schema import tool_schema
from app.agents.investigation.workflow import validate_submission
from test_investigation import ScriptedClient, submission, turn


class InvestigationDecisionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.BackendIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        with sqlite3.connect(self.fixture.database) as db:
            db.execute("ALTER TABLE alerts ADD COLUMN kind")
            db.execute("ALTER TABLE alerts ADD COLUMN transfer_id")
            db.execute("UPDATE alerts SET kind='transfer',transfer_id='CK00001'")
            db.execute("UPDATE transfers SET simo_flag='True',amount='639000' WHERE transfer_id='CK00001'")

    def read(self):
        tools = self.fixture.tools()
        result = tools.call("get_transfer", {"transfer_id": "CK00001"})
        self.assertTrue(result["ok"], result)
        return tools, ToolStep(tool_call_id="transfer-read", name="get_transfer", result=result)

    def case(self, recommendation="hold", **changes):
        return submission("transfer-read", verdict="inconclusive", confidence=0.31,
                          missing_information=["Whether the borrower was instructed to send money"],
                          transaction_assessments=[{
                              "transfer_id": "CK00001", "recommendation": recommendation,
                              "reason": "SIMO flag is recorded; verify with the authorized team",
                              "evidence": [{"claim": "Recorded transfer warning", "source": "transfer-read"}],
                          }], **changes)

    def test_trigger_and_hard_signal_survive_even_below_rapid_outflow_threshold(self):
        tools, step = self.read()
        cluster = tools.call("get_cluster", {})["data"]
        self.assertEqual(cluster["triggering_transfer_id"], "CK00001")
        transaction = step.result["data"]["transfer"]
        self.assertTrue(transaction["simo_flag"])
        self.assertEqual(transaction["transfer_loan_ratio"], 0.639)
        self.assertEqual(transaction["reported_recipient_count"], 1)
        self.assertEqual(transaction["report_ids"], ["R1"])
        reports = tools.call("reports_mentioning", {})["data"]["reports"]
        self.assertIn(transaction["recipient_node_id"], reports[0]["matched_recipient_node_ids"])
        flow = tools.call("money_flow", {})["data"]
        self.assertEqual(flow["fast_out_stranger"], [])
        self.assertEqual(flow["simo_flagged_transfer_ids"], ["CK00001"])
        self.assertEqual(flow["transfers"][0]["simo_flag"], True)
        self.assertFalse(tools.call("get_transfer", {"transfer_id": "CK00002"})["ok"])
        for private in ("PRIVATE", "001234567890", "0900000001", "012345678901"):
            self.assertNotIn(private, json.dumps(step.result))

    def test_inconclusive_borrower_and_grounded_transfer_action_coexist(self):
        tools, step = self.read()
        case = validate_submission(self.case(), [step])
        tools.validate_case(case, [step])
        self.assertEqual(case.confidence, 0.31)
        self.assertEqual(case.members, [])
        self.assertEqual(case.victims, [])
        self.assertEqual(case.transaction_assessments[0].recommendation, "hold")

    def test_unread_transfer_or_unrelated_evidence_cannot_support_action(self):
        tools, step = self.read()
        cluster = ToolStep(tool_call_id="cluster", name="get_cluster", result=tools.call("get_cluster", {}))
        args = self.case()
        args["transaction_assessments"][0]["evidence"][0]["source"] = "cluster"
        with self.assertRaisesRegex(ValueError, "exact transfer"):
            tools.validate_case(validate_submission(args, [cluster, step]), [cluster, step])
        with self.assertRaisesRegex(ValueError, "Read triggering_transfer_id"):
            tools.validate_case(validate_submission(submission("cluster"), [cluster]), [cluster])

    def test_hold_without_recorded_warning_is_rejected(self):
        with sqlite3.connect(self.fixture.database) as db:
            db.execute("UPDATE transfers SET simo_flag='False'")
            db.execute("DELETE FROM reports")
        tools, step = self.read()
        with self.assertRaisesRegex(ValueError, "recorded recipient warning"):
            tools.validate_case(validate_submission(self.case(), [step]), [step])
        tools.validate_case(validate_submission(self.case("review"), [step]), [step])

    def test_mock_number_only_report_matches_do_not_become_a_verified_warning(self):
        with sqlite3.connect(self.fixture.database) as db:
            db.execute("UPDATE transfers SET simo_flag='False'")
        tools, step = self.read()
        transaction = step.result["data"]["transfer"]
        self.assertEqual(transaction["reported_recipient_count"], 1)
        self.assertEqual(transaction["verified_reported_recipient_count"], 0)
        with self.assertRaisesRegex(ValueError, "verified scope"):
            tools.validate_case(validate_submission(self.case(), [step]), [step])
        tools.validate_case(validate_submission(self.case("review"), [step]), [step])

    def test_simo_does_not_allow_unqualified_allow_or_no_missing_information(self):
        tools, step = self.read()
        with self.assertRaisesRegex(ValueError, "SIMO warning"):
            tools.validate_case(validate_submission(self.case("allow"), [step]), [step])
        args = self.case()
        args["missing_information"] = []
        with self.assertRaisesRegex(ValueError, "missing_information"):
            tools.validate_case(validate_submission(args, [step]), [step])

    def test_workflow_repairs_generic_conclusion_instead_of_accepting_it(self):
        model = ScriptedClient(turn("transfer-read", "get_transfer", {"transfer_id": "CK00001"}),
                               turn("invalid-finish", "submit_case", submission("transfer-read")),
                               turn("finish", "submit_case", self.case()))
        client = self.fixture.client(model)
        response = client.get("/api/alerts/AL1/investigate")
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        case = events[-1]["case"]
        self.assertEqual(case["status"], "completed")
        self.assertEqual(case["confidence"], 0.31)
        self.assertEqual(case["transaction_assessments"][0]["transfer_id"], "CK00001")
        self.assertFalse(case["tool_steps"][1]["result"]["ok"])
        self.assertTrue(case["tool_steps"][2]["result"]["ok"])

    def test_reports_are_joined_for_all_transfers_even_same_name_or_late(self):
        with sqlite3.connect(self.fixture.database) as db:
            db.execute("UPDATE transfers SET to_name='PRIVATE NAME' WHERE transfer_id='CK00001'")
        tools, step = self.read()
        self.assertTrue(step.result["data"]["transfer"]["recipient_name_matches_applicant"])
        self.assertEqual(step.result["data"]["transfer"]["reported_recipient_count"], 1)
        self.assertEqual(len(tools.call("reports_mentioning", {})["data"]["reports"]), 1)

    def test_bank_scope_and_pagination_do_not_mix_recipient_identities(self):
        with sqlite3.connect(self.fixture.database) as db:
            db.execute("INSERT INTO transfers SELECT 'CK00003',from_wallet,to_id,to_name,'BIDV',to_type,amount,"
                       "created_at,recipient_in_contacts,contact_saved_minutes_ago,prior_transfers_to_recipient,"
                       "simo_flag,to_wallet_age_days,note FROM transfers WHERE transfer_id='CK00001'")
        tools = self.fixture.tools()
        page = tools.call("money_flow", {"limit": 1})["data"]
        self.assertTrue(page["truncated"])
        following = tools.call("money_flow", {"limit": 1, "offset": page["next_offset"]})["data"]
        self.assertFalse(following["truncated"])
        first = page["transfers"][0]["recipient_node_id"]
        second = following["transfers"][0]["recipient_node_id"]
        self.assertNotEqual(first, second)
        self.assertEqual(len(tools.call("account_senders", {"node_id": first})["data"]["senders"]), 1)

    def test_provider_schema_simplification_keeps_local_limits(self):
        original = submit_definition()["parameters"]
        provider = tool_schema(original)
        self.assertEqual(original["properties"]["transaction_assessments"]["maxItems"], 50)
        self.assertNotIn("maxItems", provider["properties"]["transaction_assessments"])
        self.assertEqual(original["required"], provider["required"])
        self.assertEqual(original["$defs"]["TransactionAssessment"]["required"],
                         provider["$defs"]["TransactionAssessment"]["required"])
        args = self.case()
        args["transaction_assessments"] *= 51
        with self.assertRaises(ValidationError):
            CaseSubmission.model_validate(args)

    def test_empty_snapshot_is_an_execution_failure_not_an_uncertain_analysis(self):
        with sqlite3.connect(self.fixture.database) as db:
            db.execute("UPDATE apps SET applied_at='2026-12-01T00:00:00'")
        model = ScriptedClient()
        client = self.fixture.client(model)
        response = client.get("/api/alerts/AL1/investigate")
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        self.assertEqual(events[-1]["case"]["status"], "failed")
        self.assertEqual(events[-1]["case"]["reason"], "snapshot_empty")
        self.assertEqual(model.history, [])
        self.assertEqual(client.app.state.backend_tools.q("SELECT * FROM cases"), [])
