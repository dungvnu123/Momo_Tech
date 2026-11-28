import json
from pathlib import Path
from app.agents.investigation import InvestigationAgent
from app.types.schemas import AgentContext
from app.backend import mock_ai
from app.backend.agent_tools import BackendAgentTools


async def investigate(self, alert):
    if not self.ready():
        for event in mock_ai.investigate(alert, self.store, alert["ts"]):
            yield event
        return
    tools = BackendAgentTools(self.store, alert)
    if not tools.ids:
        yield {
            "type": "case",
            "case": {
                "verdict": "inconclusive",
                "confidence": 0,
                "members": [],
                "victims": [],
                "evidence": [],
                "actions": [],
                "mode": "gemini",
                "status": "failed",
                "reason": "snapshot_empty",
                "missing_information": ["Không có hồ sơ hợp lệ tại thời điểm cảnh báo."],
            },
        }
        return
    agent = InvestigationAgent(self.client, tools_factory=lambda: tools, require_assessments=True)
    agent.prompt_file = Path(__file__).resolve().parents[1] / "investigation_prompt.md"
    context = AgentContext(metadata={"cluster_id": alert["cluster_id"]})
    async for event, data in agent._events(tools.ids[0], context):
        if event == "model_step":
            yield {
                "type": "step",
                "tool": None,
                "thought": "Đang chọn bước kiểm tra tiếp theo.",
                "result": ", ".join(data["requested_tools"]),
            }
        elif event == "tool_result":
            yield {
                "type": "step",
                "tool": data["name"],
                "thought": "Đối chiếu dữ liệu tại thời điểm cảnh báo.",
                "result": json.dumps(data["result"], ensure_ascii=False),
            }
        elif event == "done":
            case = {
                **data["case"],
                "evidence": [
                    e["claim"] + " [" + e["source"] + "]" for e in data["case"]["evidence"]
                ],
                "cluster_id": alert["cluster_id"],
                "as_of": alert["ts"],
                "mode": "gemini",
                "run_id": data["run_id"],
                "status": data["status"],
                "reason": data["reason"],
            }
            case["source_evidence"] = data["case"]["evidence"]
            case["tool_steps"] = data["steps"]
            case["model_turns"] = data["model_turns"]
            if data["status"] == "completed":
                from app.backend.cases.repository import persist_case

                persist_case(self.store, alert, case)
            yield {"type": "case", "case": case}
