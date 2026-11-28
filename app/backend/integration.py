"""Translate the web API contracts to the shared AI services and BaseAgent.
Chưa cấu hình Gemini (LLM_API_KEY trống) → mọi chức năng rơi về bản luật giả lập (mock_ai) thay vì trả 503 — demo chạy được không cần khoá."""
import json
from pathlib import Path

from app.agents.investigation import InvestigationAgent
from app.ai.transfer.schemas import TransferCheck
from app.types.schemas import AgentContext

from . import mock_ai
from .agent_tools import BackendAgentTools
from .report_view import report_view

RULES = "luật (chưa cấu hình AI)"


class BackendAI:
    def __init__(self, service, client, store):
        self.service, self.client, self.store = service, client, store

    def ready(self):
        try:
            self.client.ensure_ready()
            return True
        except Exception:
            return False

    async def analyze_report(self, text):
        if not self.ready():
            return {**mock_ai.analyze_report(text), "mode": RULES}
        result = await self.service.analyze_report(text)
        return report_view(result)

    async def check_transfer(self, ctx):
        if not self.ready():
            return {**mock_ai.check_transfer(ctx), "mode": RULES}
        request = TransferCheck(loan_amount=ctx["loan_amount"], transfer_amount=ctx["amount"],
                                minutes_after_disbursal=max(0, ctx["minutes_after_disbursal"]),
                                recipient_name_matches=ctx["to_name_matches_borrower"],
                                recipient_in_contacts=ctx["recipient_in_contacts"],
                                contact_saved_minutes_ago=ctx["contact_saved_minutes_ago"],
                                prior_transfers_to_recipient=ctx["prior_transfers_to_recipient"],
                                simo_flag=ctx["simo_flag"], reported_recipient_count=ctx["times_reported"],
                                recipient_ring_senders=(ctx.get("ring_case") or {}).get("n_senders", 0),
                                share_of_balance=min(1, ctx["amount"] / ctx["balance"]) if ctx.get("balance") else None,
                                note_tags=mock_ai.note_tags(ctx.get("note")),
                                unverified_case_count=ctx.get("unverified_case_count",0),
                                unscoped_report_count=ctx.get("unscoped_report_count",0),
                                customer_says_coached=bool(ctx.get("coached")))
        result = await self.service.check_transfer(request)
        return {**result.model_dump(), "message_for_customer": result.advice, "mode": "gemini"}

    async def investigate(self, alert):
        if not self.ready():
            for event in mock_ai.investigate(alert, self.store, alert["ts"]):
                yield event
            return
        tools = BackendAgentTools(self.store, alert)
        if not tools.ids:
            yield {"type": "case", "case": {"verdict": "inconclusive", "confidence": 0,
                   "members": [], "victims": [], "evidence": [], "actions": [], "mode": "gemini",
                   "status": "failed", "reason": "snapshot_empty", "missing_information": ["Không có hồ sơ hợp lệ tại thời điểm cảnh báo."]}}
            return
        agent = InvestigationAgent(self.client, tools_factory=lambda: tools, require_assessments=True)
        agent.prompt_file = Path(__file__).with_name("investigation_prompt.md")
        context = AgentContext(metadata={"cluster_id": alert["cluster_id"]})
        async for event, data in agent._events(tools.ids[0], context):
            if event == "model_step":
                yield {"type": "step", "tool": None, "thought": "Đang chọn bước kiểm tra tiếp theo.",
                       "result": ", ".join(data["requested_tools"])}
            elif event == "tool_result":
                yield {"type": "step", "tool": data["name"], "thought": "Đối chiếu dữ liệu tại thời điểm cảnh báo.",
                       "result": json.dumps(data["result"], ensure_ascii=False)}
            elif event == "done":
                case = {**data["case"], "evidence": [e["claim"] + " [" + e["source"] + "]" for e in data["case"]["evidence"]],
                        "cluster_id": alert["cluster_id"], "as_of": alert["ts"], "mode": "gemini",
                        "run_id": data["run_id"], "status": data["status"], "reason": data["reason"]}
                case["source_evidence"] = data["case"]["evidence"]
                case["tool_steps"] = data["steps"]
                case["model_turns"] = data["model_turns"]
                if data["status"] == "completed":
                    from .events.results import persist_case
                    persist_case(self.store, alert, case)
                yield {"type": "case", "case": case}
