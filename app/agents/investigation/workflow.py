import asyncio
import json
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from app.services.tool_llm import ModelTurn, ToolMessage
from app.tools import GraphTools

from .schemas import CaseSubmission, ToolStep, submit_definition


class InvestigationState(TypedDict):
    messages: list[ToolMessage]
    tools: GraphTools
    calls: list
    steps: list[ToolStep]
    turns: int
    case: CaseSubmission | None
    reason: str | None
    events: list[dict]


def known_applications(steps: list[ToolStep]) -> set[str]:
    identifiers = set()
    for step in steps:
        if not step.result.get("ok"):
            continue
        data = step.result.get("data", {})
        if data.get("app_id"):
            identifiers.add(data["app_id"])
        identifiers.update(data.get("app_ids", []))
        for report in data.get("reports", []):
            identifiers.update(report.get("reporter_app_ids", []))
        for record in (data.get("application", {}), data.get("record", {})):
            if record.get("app_id"):
                identifiers.add(record["app_id"])
        for node in data.get("nodes", []):
            if node.get("kind") == "Application":
                identifiers.add(node["node_id"].removeprefix("app:"))
    return identifiers


def validate_submission(arguments: dict, steps: list[ToolStep]) -> CaseSubmission:
    case = CaseSubmission.model_validate(arguments)
    sources = {step.tool_call_id for step in steps if step.result.get("ok") and step.name != "submit_case"}
    if any(evidence.source not in sources for evidence in case.evidence):
        raise ValueError("Evidence must reference a successful read in this run")
    if any(evidence.source not in sources for item in case.transaction_assessments for evidence in item.evidence):
        raise ValueError("Transaction evidence must reference a successful read in this run")
    if not (set(case.members) | set(case.victims)) <= known_applications(steps):
        raise ValueError("Case mentions an application not observed in tool data")
    protected = set()
    for step in steps:
        if not step.result.get("ok"):
            continue
        data = step.result.get("data", {})
        if data.get("victim_self_report_count", 0) > 0:
            protected.add(data.get("application", {}).get("app_id"))
        for report in data.get("reports", []):
            if report.get("reporter_is_victim"):
                protected.update(report.get("reporter_app_ids", []))
    if set(case.members) & protected:
        raise ValueError("An application with victim self-report evidence cannot be submitted as an offender; use victims or inconclusive pending review")
    return case


def create_workflow(client, *, max_tool_calls: int, operation_timeout: float):
    async def model_node(state: InvestigationState):
        remaining = max_tool_calls - len(state["steps"])
        definitions = [submit_definition()] if remaining == 1 else state["tools"].definitions + [submit_definition()]
        first = state["messages"][0]
        messages = [first.model_copy(update={"content": first.content + f"\nNgân sách còn {remaining} tool call, tính cả submit_case. "
                                         "Lượt cuối chỉ được nộp kết luận; nếu thiếu dữ liệu chọn inconclusive."}), *state["messages"][1:]]
        response = await asyncio.wait_for(client.complete(messages, definitions), operation_timeout)
        response = ModelTurn.model_validate(response)
        ids = [call.id for call in response.tool_calls]
        previous = {step.tool_call_id for step in state["steps"]}
        reason = None
        if not ids:
            reason = "model_did_not_call_tool"
        elif len(set(ids)) != len(ids) or previous.intersection(ids):
            reason = "reused_tool_call_id"
        elif any(call.name == "submit_case" for call in response.tool_calls) and len(ids) != 1:
            reason = "terminal_tool_must_be_alone"
        elif len(state["steps"]) + len(ids) > max_tool_calls:
            reason = "max_tool_calls_reached"
        elif remaining == 1 and any(call.name != "submit_case" for call in response.tool_calls):
            reason = "max_tool_calls_reached"
        return {
            "messages": [*state["messages"], ToolMessage(role="assistant", content=response.text,
                                                       tool_calls=response.tool_calls,
                                                       provider_content=response.provider_content)],
            "calls": response.tool_calls, "turns": state["turns"] + 1, "reason": reason,
            "events": [{"event": "model_step", "data": {"turn": state["turns"] + 1,
                        "requested_tools": [call.name for call in response.tool_calls]}}],
        }

    async def tools_node(state: InvestigationState):
        messages, steps, events = list(state["messages"]), list(state["steps"]), []
        case = None
        call = state["calls"][0]
        if call.name == "submit_case":
            try:
                candidate = validate_submission(call.arguments, steps)
                if hasattr(state["tools"], "validate_case"):
                    state["tools"].validate_case(candidate, steps)
                case = candidate
                result = {"ok": True, "tool": call.name, "data": {"accepted": True}}
            except ValidationError as error:
                result = {"ok": False, "tool": call.name, "error": {"code": "invalid_case",
                          "message": "Correct the listed fields to match submit_case schema",
                          "fields": [{"field": ".".join(map(str, item["loc"])), "code": item["type"], "message": item["msg"]}
                                     for item in error.errors(include_input=False, include_url=False)]}}
            except ValueError as error:
                result = {"ok": False, "tool": call.name,
                          "error": {"code": "invalid_case", "message": str(error)}}
            if not result["ok"]:
                result["available_evidence_sources"] = [
                    step.tool_call_id for step in steps if step.result.get("ok") and step.name != "submit_case"
                ]
                result["observed_app_ids"] = sorted(known_applications(steps))
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(state["tools"].call, call.name, call.arguments), operation_timeout,
            )
        result = {**result, "tool_call_id": call.id}
        step = ToolStep(tool_call_id=call.id, name=call.name, result=result)
        steps.append(step)
        messages.append(ToolMessage(role="tool", tool_call_id=call.id,
                                    content=json.dumps(result, ensure_ascii=False)))
        events.append({"event": "tool_result", "data": step.model_dump(mode="json")})
        reason = "max_tool_calls_reached" if case is None and len(steps) >= max_tool_calls else None
        return {"messages": messages, "steps": steps, "case": case, "reason": reason,
                "calls": state["calls"][1:], "events": events}

    def after_model(state):
        return END if state["reason"] else "tools"

    def after_tools(state):
        if state["case"] is not None or state["reason"]:
            return END
        return "tools" if state["calls"] else "model"

    graph = StateGraph(InvestigationState)
    graph.add_node("model", model_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("model")
    graph.add_conditional_edges("model", after_model)
    graph.add_conditional_edges("tools", after_tools)
    return graph.compile()
