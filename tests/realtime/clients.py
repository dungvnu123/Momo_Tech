import json
from app.services.tool_llm import ModelTurn, ToolCall


class RealtimeClient:
    def __init__(self, *, skip=False):
        self.calls, self.skip = ([], skip)

    def ensure_ready(self):
        pass

    async def complete(self, messages, definitions):
        reads = [json.loads(m.content) for m in messages if m.role == "tool"]
        names = {d["name"] for d in definitions}
        if "triage" in names:
            payload = json.loads(next((m.content for m in messages if m.role == "user")))
            name, args = (
                "triage",
                {
                    "decisions": [
                        {
                            "cluster_id": c["cluster_id"],
                            "decision": "skip" if self.skip else "investigate",
                            "reason": "Review source-linked new activity",
                        }
                        for c in payload["clusters"]
                    ]
                },
            )
        elif not reads:
            name, args = ("get_cluster", {})
        elif len(reads) == 1:
            name, args = ("cluster_money_flow", {})
        elif reads[0]["data"].get("triggering_transfer_id") and len(reads) == 2:
            name, args = (
                "get_transfer",
                {"transfer_id": reads[0]["data"]["triggering_transfer_id"]},
            )
        else:
            scope = reads[1]
            proof = {
                "claim": "The scoped records require verification",
                "source": scope["tool_call_id"],
            }
            args = {
                "verdict": "inconclusive",
                "confidence": 0.4,
                "members": [],
                "victims": [],
                "summary": "New transfer activity needs human verification",
                "evidence": [proof],
                "benign_explanation": "An ordinary payment remains possible",
                "missing_information": ["Ask the customer"],
                "actions": ["Verify recipient and customer intent"],
                "cluster_assessment": {
                    "level": "suspicious",
                    "reason": "New source-linked activity",
                    "evidence": [proof],
                    "limitations": ["Reports and roles remain unverified"],
                },
                "application_assessments": [
                    {
                        "app_id": a["app_id"],
                        "role": "undetermined",
                        "reason": "Observed loan snapshot",
                        "evidence": [{**proof, "record_ids": [a["record_id"]]}],
                        "missing_information": ["Verify intent"],
                    }
                    for a in scope["data"]["application_summaries"]
                ],
            }
            focused = reads[0]["data"].get("triggering_transfer_id")
            if focused:
                args["transaction_assessments"] = [
                    {
                        "transfer_id": focused,
                        "recommendation": "review",
                        "reason": "Check actual transfer state",
                        "evidence": [
                            {
                                "claim": "Exact triggering transaction",
                                "source": reads[2]["tool_call_id"],
                            }
                        ],
                    }
                ]
            name = "submit_case"
        self.calls.append(name)
        return ModelTurn(
            tool_calls=[ToolCall(id=f"live-call-{len(self.calls)}", name=name, arguments=args)]
        )
