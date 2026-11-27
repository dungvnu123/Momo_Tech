from time import perf_counter
import hashlib

from app.agents.investigation import InvestigationAgent
from app.types.schemas import AgentContext


async def investigate_groups(client, database, groups, decisions, limit, directory, *, on_result=None):
    by_id = {item.cluster_id: item for item in decisions}
    agent = InvestigationAgent(client, database=database)
    result, investigated = [], 0
    for group in groups:
        decision = by_id[group["cluster_id"]]
        item = {**group, "triage": decision.model_dump()}
        if decision.decision == "skip":
            result.append({**item, "status": "skipped_by_triage"})
            if on_result:
                on_result(list(result))
            continue
        if investigated >= limit:
            result.append({**item, "status": "deferred_by_limit"})
            if on_result:
                on_result(list(result))
            continue
        investigated += 1
        started = perf_counter()
        run = await agent.investigate(group["app_ids"][0], AgentContext(metadata={"cluster_id": group["cluster_id"]}))
        trace_file = "trace-" + hashlib.sha256(group["cluster_id"].encode()).hexdigest()[:24] + ".json"
        (directory / trace_file).write_text(run.model_dump_json(indent=2), encoding="utf-8")
        result.append({**item, "status": run.status, "reason": run.reason, "case": run.case.model_dump(),
                       "run_id": run.run_id, "trace_file": trace_file, "tool_calls": len(run.steps), "model_turns": run.model_turns,
                       "elapsed_seconds": round(perf_counter() - started, 3),
                       "evidence_count": len(run.case.evidence),
                       "failed_tool_calls": sum(not step.result.get("ok") for step in run.steps),
                       "evidence_valid": all(e.source in {s.tool_call_id for s in run.steps
                                               if s.result.get("ok") and s.name != "submit_case"} for e in run.case.evidence)})
        if on_result:
            on_result(list(result))
    return result
