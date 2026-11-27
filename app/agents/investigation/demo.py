import json

from app.services.tool_llm import ModelTurn, ToolCall


class DemoInvestigationClient:
    def ensure_ready(self):
        pass

    async def complete(self, messages, tools):
        responses = [message for message in messages if message.role == "tool"]
        app_id = messages[1].content.split("app_id=", 1)[1].splitlines()[0].removesuffix(".")
        stage = len(responses)
        name, arguments = "get_application", {"app_id": app_id}
        if stage:
            latest = json.loads(responses[-1].content)
            if not latest["ok"]:
                stage = 4
        if stage == 1:
            name, arguments = "money_flow", {"app_id": app_id, "limit": 5}
        elif stage == 2:
            application = json.loads(responses[0].content)["data"]["application"]
            name, arguments = "neighbors", {
                "node_id": application.get("device_node_id", "app:" + app_id),
                "edge_type": "USES_DEVICE", "direction": "incoming", "limit": 5,
            }
        elif stage == 3:
            edges = json.loads(responses[-1].content)["data"]["edges"]
            if edges:
                name, arguments = "get_evidence", {"edge_id": edges[0]["edge_id"]}
            else:
                stage = 4
        if stage >= 4:
            successful = [response for response in responses if json.loads(response.content)["ok"]]
            name, arguments = "submit_case", {
                "verdict": "inconclusive", "confidence": 0,
                "benign_explanation": "Bản demo chỉ kiểm tra luồng đọc dữ liệu, chưa đánh giá gian lận.",
                "evidence": [{"claim": "Đã truy xuất dữ liệu qua tool trong bản demo.",
                              "source": successful[-1].tool_call_id}] if successful else [],
            }
        return ModelTurn(tool_calls=[ToolCall(id=f"demo-{len(responses) + 1}", name=name, arguments=arguments)])
