import asyncio
import csv
import json
from app import db as pgdb
import unittest

from pydantic import ValidationError

import test_backend_integration as backend_fixture
import test_graph_tools as graph_fixture
from app.agents.investigation import InvestigationAgent
from app.agents.investigation.assessments import validate_assessments
from app.agents.investigation.schemas import CaseSubmission, ToolStep
from app.graph import build_graph
from app.graph.ai_store import AIStore
from app.ai.shield.schemas import ReportAnalysis
from app.tools import GraphTools
from test_investigation import ScriptedClient, turn


def assessment_case(source="scope", record_id="applications:A", *, app="A", role="undetermined"):
    return {
        "verdict": "inconclusive", "confidence": .43, "members": [], "victims": [],
        "evidence": [{"claim": "Scope was inspected", "source": source}],
        "benign_explanation": "Considered ordinary payments and household device sharing",
        "missing_information": ["Customer explanation and recipient verification"],
        "cluster_assessment": {"level": "suspicious", "reason": "Shared recipient pattern needs checking",
            "evidence": [{"claim": "Observed cluster-wide money flows", "source": source}],
            "limitations": ["Source and role verification remain incomplete"]},
        "application_assessments": [{"app_id": app, "role": role, "reason": "Application observations are not proof of intent",
            "evidence": [{"claim": "Application-specific flow summary", "source": source, "record_ids": [record_id]}],
            "missing_information": ["Verify actual intent and ownership"]}],
    }


class ClusterAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = graph_fixture.GraphToolTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        path = self.fixture.directory / "wallet_transfers.csv"
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        extra = {**rows[1], "transfer_id": "T3", "from_wallet": "0900000002", "amount": "900000"}
        rows.append(extra)
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        report = self.fixture.directory / "scam_reports.csv"
        with report.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        rows[0]["raw_text"] = "I was tricked into sending money to ACB 001234567890"
        with report.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        build_graph(self.fixture.directory, self.fixture.database, replace=True)
        with AIStore(self.fixture.database) as store:
            store.persist_report("R1", rows[0]["raw_text"], ReportAnalysis(
                verdict="scam", confidence=.8, reporter_is_victim=True,
                indicators=[{"kind": "bank_account", "raw": "001234567890", "bank": "ACB"}],
                reasons=["Customer describes a scam"], advice="Verify recipient"))
        self.tools = GraphTools(self.fixture.database)

    def scope_step(self, **options):
        result = self.tools.cluster_money_flow(app_ids=["A", "B"], **options)
        self.assertTrue(result["ok"], result)
        return ToolStep(tool_call_id="scope", name="cluster_money_flow", result=result)

    def test_aggregate_totals_and_shared_recipients_cover_all_evidence_pages(self):
        step = self.scope_step(limit=1)
        data = step.result["data"]
        self.assertEqual(data["totals"]["loan_amount"], 2000000)
        self.assertEqual(data["totals"]["transfer_count"], 3)
        self.assertEqual(data["totals"]["transfer_amount"], 1500000)
        self.assertEqual(data["totals"]["shared_recipient_count"], 1)
        self.assertEqual(data["recipients"][0]["sender_app_ids"], ["A", "B"])
        self.assertTrue(data["truncated"])
        self.assertEqual(len(data["transfers"]), 1)
        page = self.tools.cluster_money_flow(app_ids=["A", "B"], limit=1, offset=data["next_offset"])["data"]
        self.assertEqual(page["totals"], data["totals"])
        self.assertNotEqual(page["transfers"][0]["record_id"], data["transfers"][0]["record_id"])
        by_app = {r["app_id"]: r for r in data["application_summaries"]}
        self.assertEqual(by_app["A"]["rapid_stranger_amount"], 300000)
        self.assertEqual(by_app["B"]["rapid_stranger_amount"], 900000)
        self.assertEqual(by_app["A"]["victim_self_report_count"], 1)

    def test_summary_preserves_sources_without_raw_personal_identifiers(self):
        data = self.scope_step().result["data"]
        for t in data["transfers"]:
            self.assertEqual(t["record_id"], "wallet_transfers:" + t["source"]["id"])
            self.assertTrue(t["edge_id"])
        self.assertEqual(data["reports"][0]["reporter_app_ids"], ["A"])
        self.assertEqual(data["reports"][0]["related_app_ids"], ["A", "B"])
        for private in ("0900000001", "0900000002", "001234567890", "012345678901", "Private address", "Nguyễn Văn An"):
            self.assertNotIn(private, json.dumps(data, ensure_ascii=False))

    def test_suspicious_cluster_and_unknown_individual_are_independent(self):
        result = validate_assessments(CaseSubmission.model_validate(assessment_case()), [self.scope_step()], ["A", "B"], required=True)
        self.assertEqual(result.verdict, "inconclusive")
        self.assertEqual(result.cluster_assessment.level, "suspicious")
        self.assertEqual(result.confidence, .43)
        self.assertEqual(result.application_assessments[0].verification_status, "unverified")
        unassessed = next(r for r in result.application_assessments if r.app_id == "B")
        self.assertEqual(unassessed.assessment_status, "not_assessed")
        self.assertEqual(unassessed.role, "undetermined")
        self.assertEqual(unassessed.evidence, [])

    def test_other_person_or_invented_record_cannot_support_a_role(self):
        step = self.scope_step()
        for record_id in ("applications:B", "applications:unknown"):
            with self.assertRaises(ValueError):
                validate_assessments(CaseSubmission.model_validate(assessment_case(record_id=record_id)), [step], ["A", "B"], required=True)
        case = assessment_case()
        case["application_assessments"][0]["evidence"][0]["record_ids"] = []
        with self.assertRaisesRegex(ValueError, "attributed"):
            validate_assessments(CaseSubmission.model_validate(case), [step], ["A", "B"], required=True)

    def test_victim_self_report_blocks_suspected_participant_but_not_review(self):
        with self.assertRaisesRegex(ValueError, "self-report"):
            validate_assessments(CaseSubmission.model_validate(assessment_case(role="suspected_participant")), [self.scope_step()], ["A", "B"], required=True)
        case = assessment_case(role="possible_victim", record_id="ai_report_analysis:R1")
        result = validate_assessments(CaseSubmission.model_validate(case), [self.scope_step()], ["A", "B"], required=True)
        self.assertEqual(result.application_assessments[0].role, "possible_victim")

    def test_verified_status_and_duplicate_or_outside_scope_assessments_are_rejected(self):
        case = assessment_case()
        case["application_assessments"][0]["verification_status"] = "verified"
        with self.assertRaises(ValidationError):
            CaseSubmission.model_validate(case)
        for outside in (True, False):
            case = assessment_case()
            if outside:
                case["application_assessments"][0]["app_id"] = "outside"
            else:
                case["application_assessments"] *= 2
            with self.assertRaises(ValueError):
                validate_assessments(CaseSubmission.model_validate(case), [self.scope_step()], ["A", "B"], required=True)

    def test_full_scope_read_and_limitations_are_required(self):
        partial = ToolStep(tool_call_id="scope", name="cluster_money_flow",
            result=self.tools.cluster_money_flow(app_ids=["A"]))
        with self.assertRaisesRegex(ValueError, "entire requested scope"):
            validate_assessments(CaseSubmission.model_validate(assessment_case()), [partial], ["A", "B"], required=True)
        case = assessment_case()
        case["cluster_assessment"]["limitations"] = []
        with self.assertRaisesRegex(ValueError, "truncated"):
            validate_assessments(CaseSubmission.model_validate(case), [self.scope_step(limit=1)], ["A", "B"], required=True)

    def test_graph_tool_requires_one_bounded_distinct_scope(self):
        for args in ({}, {"app_ids": ["A", "A"]}, {"app_ids": ["A"], "cluster_id": "C1"},
                     {"app_ids": [str(i) for i in range(101)]}):
            self.assertFalse(self.tools.call("cluster_money_flow", args)["ok"])
        self.assertFalse(self.tools.cluster_money_flow(cluster_id="C1", app_ids=["A"])["ok"])

    def test_agent_rejects_unread_scope_then_repairs_with_attributed_result(self):
        client = ScriptedClient(
            turn("bad", "submit_case", assessment_case(source="scope")),
            turn("scope", "cluster_money_flow", {"app_ids": ["A"]}),
            turn("final", "submit_case", assessment_case(source="scope")),
        )
        agent = InvestigationAgent(client, database=self.fixture.database, require_assessments=True)
        result = asyncio.run(agent.investigate("A"))
        self.assertEqual(result.status, "completed")
        self.assertFalse(result.steps[0].result["ok"])
        self.assertEqual(result.case.cluster_assessment.level, "suspicious")
        self.assertEqual(result.case.application_assessments[0].evidence[0].record_ids, ["applications:A"])

    def test_backend_snapshot_excludes_future_records_and_preserves_attribution(self):
        fixture = backend_fixture.BackendIntegrationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        tools = fixture.tools()
        data = tools.call("cluster_money_flow", {})["data"]
        self.assertEqual(data["totals"]["transfer_count"], 1)
        self.assertEqual(data["transfers"][0]["record_id"], "transfers:CK00001")
        self.assertEqual([r["report_id"] for r in data["reports"]], ["R1"])
        self.assertEqual(data["coverage"]["as_of"], "2026-11-01T09:00:00")
        self.assertFalse(tools.call("cluster_money_flow", {"app_ids": ["A", "A"]})["ok"])
        with pgdb.connect(fixture.database) as db:
            db.execute("UPDATE apps SET full_name=''")
            db.execute("UPDATE transfers SET to_name=''")
        unknown = tools.call("cluster_money_flow", {})["data"]
        self.assertEqual(unknown["application_summaries"][0]["unknown_name_amount"], 900000)
