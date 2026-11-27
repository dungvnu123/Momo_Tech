from app.agents.investigation import InvestigationAgent
from app.types.schemas import AgentContext


async def evaluate_investigations(client, database, data_dir, expected_cases, investigation_limit):
    investigations = []
    if investigation_limit:
        positives = [item for item in expected_cases if item["verdict"] == "fraud_ring"]
        victims = [item for item in expected_cases if item["verdict"] == "victims"]
        benign = [item for item in expected_cases if item["verdict"] == "benign"]
        ordered = positives[:2] + victims[:1] + benign + positives[2:] + victims[1:]
        agent = InvestigationAgent(client, database=database)
        for item in ordered[:investigation_limit]:
            result = await agent.investigate(item["app_ids"][0], AgentContext(metadata={"cluster_id": item["cluster_id"]}))
            traces = data_dir / "ai-investigations"
            traces.mkdir(parents=True, exist_ok=True)
            (traces / f"{result.app_id}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
            investigations.append({"app_id": result.app_id, "expected": item["verdict"],
                                   "actual": result.case.verdict, "correct": result.case.verdict == item["verdict"],
                                   "status": result.status, "reason": result.reason, "tool_calls": len(result.steps),
                                   "model_turns": result.model_turns,
                                   "evidence_valid": all(evidence.source in {
                                       step.tool_call_id for step in result.steps if step.result.get("ok") and step.name != "submit_case"
                                   } for evidence in result.case.evidence)})
    return investigations
