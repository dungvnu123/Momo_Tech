import asyncio
import logging
from contextlib import aclosing
from pathlib import Path
from uuid import uuid4

from app.agents.base import BaseAgent, format_sse
from app.services.tool_llm import ToolMessage
from app.tools import GraphTools
from app.types.schemas import AgentContext, ChatResponse

from .schemas import CaseSubmission, InvestigationRequest, InvestigationResult
from .workflow import create_workflow

logger = logging.getLogger(__name__)


class InvestigationAgent(BaseAgent):
    agent_id = "investigation"
    name = "Thám tử"
    prompt_file = Path(__file__).with_name("prompt.md")

    def __init__(self, llm_client, *, database="data/graph.db", max_tool_calls=12,
                 timeout_seconds=180.0, operation_timeout=30.0, tools_factory=None, require_assessments=False):
        super().__init__(llm_client, timeout_seconds=timeout_seconds)
        if type(max_tool_calls) is not int or not 1 <= max_tool_calls <= 12:
            raise ValueError("max_tool_calls must be an integer from 1 to 12")
        if not 0 < operation_timeout <= timeout_seconds:
            raise ValueError("operation_timeout must be positive and within the total timeout")
        self.database = Path(database)
        self.max_tool_calls = max_tool_calls
        self.operation_timeout = operation_timeout
        self.tools_factory = tools_factory
        self.require_assessments = require_assessments

    def _get_graph(self):
        if self._graph is None:
            self._graph = create_workflow(self.llm_client, max_tool_calls=self.max_tool_calls,
                                          operation_timeout=self.operation_timeout, require_assessments=self.require_assessments)
        return self._graph

    async def _events(self, app_id: str, context: AgentContext):
        request = InvestigationRequest(app_id=app_id.removeprefix("app:"), cluster_id=context.metadata.get("cluster_id"))
        self.llm_client.ensure_ready()
        run_id = uuid4().hex
        instruction = f"Điều tra hồ sơ app_id={request.app_id}."
        if request.cluster_id:
            instruction += f"\nCụm ứng viên được cung cấp: cluster_id={request.cluster_id}."
        prompt = self.system_prompt
        if self.require_assessments:
            prompt += "\n\n" + Path(__file__).with_name("assessment_prompt.md").read_text(encoding="utf-8")
        state = {
            "app_id": request.app_id, "cluster_id": request.cluster_id,
            "messages": [ToolMessage(role="system", content=prompt),
                         ToolMessage(role="user", content=instruction)],
            "tools": self.tools_factory() if self.tools_factory else GraphTools(self.database),
            "calls": [], "steps": [], "turns": 0,
            "case": None, "reason": None, "events": [],
        }
        yield "started", {"run_id": run_id, "app_id": request.app_id}
        try:
            async with asyncio.timeout(self.timeout_seconds):
                updates = self._get_graph().astream(state, stream_mode="updates",
                                                    config={"recursion_limit": 2 * self.max_tool_calls + 4})
                async with aclosing(updates):
                    async for update in updates:
                        for values in update.values():
                            state.update(values)
                            for event in values.get("events", []):
                                yield event["event"], {"run_id": run_id, **event["data"]}
        except TimeoutError:
            state["reason"] = "operation_timeout"
        except Exception as error:
            logger.error("Investigation failed, run_id=%s", run_id)
            code = getattr(error, "code", None)
            state["reason"] = f"provider_error_{code}" if code in {400, 401, 403, 404, 429, 500, 502, 503, 504} else "execution_failed"
        case = state["case"]
        if case is None or state["reason"] is not None:
            case = CaseSubmission(verdict="inconclusive", confidence=0,
                                  benign_explanation="Chưa đủ dữ liệu để loại trừ các khả năng vô hại và kết luận.")
        reason = state["reason"]
        status = "completed" if reason is None else (
            "limit_reached" if reason == "max_tool_calls_reached" else "failed"
        )
        result = InvestigationResult(run_id=run_id, app_id=request.app_id,
                                     conversation_id=context.conversation_id, status=status,
                                     reason=reason, case=case, steps=state["steps"], model_turns=state["turns"])
        yield "done", result.model_dump(mode="json")

    async def investigate(self, app_id: str, context: AgentContext | None = None) -> InvestigationResult:
        async for event, data in self._events(app_id, context or AgentContext()):
            if event == "done":
                return InvestigationResult.model_validate(data)
        raise RuntimeError("Investigation ended without a result")

    async def run(self, message: str, context: AgentContext) -> ChatResponse:
        result = await self.investigate(message, context)
        return ChatResponse(agent_id=self.agent_id, conversation_id=context.conversation_id,
                            message=result.model_dump_json())

    async def stream(self, message: str, context: AgentContext):
        async for event, data in self._events(message, context):
            yield format_sse(event, data)
