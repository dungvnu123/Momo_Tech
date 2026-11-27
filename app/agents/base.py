import asyncio
import json
import logging
from collections.abc import AsyncIterator
from math import isfinite
from pathlib import Path
from typing import TypedDict

from fastapi.responses import PlainTextResponse, StreamingResponse
from langgraph.graph import END, StateGraph

from app.services.llm_client import LLMClient, LLMMessage
from app.types.schemas import AgentContext, ChatResponse
from app.utils import get_prompt_from_md

logger = logging.getLogger(__name__)


class AgentGraphState(TypedDict):
    messages: list[LLMMessage]
    response: str


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class BaseAgent:
    agent_id: str = "default"
    name: str = "Base Agent"
    prompt_file: Path | None = None
    fallback_system_prompt: str = ""

    def __init__(self, llm_client: LLMClient, *, timeout_seconds: float = 30.0) -> None:
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.llm_client = llm_client
        self.timeout_seconds = timeout_seconds
        self._graph = None

    @property
    def system_prompt(self) -> str:
        if self.prompt_file is None:
            return self.fallback_system_prompt
        return get_prompt_from_md(self.prompt_file, default=self.fallback_system_prompt)

    def resolve_system_prompt(self, context: AgentContext) -> str:
        return self.system_prompt

    def _build_messages(self, message: str, context: AgentContext) -> list[LLMMessage]:
        if not message.strip():
            raise ValueError("message cannot be blank")
        system_prompt = self.resolve_system_prompt(context)
        if context.system_prompt:
            system_prompt += "\n\nAdditional system instructions from request:\n" + context.system_prompt
        messages: list[LLMMessage] = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": item.role, "content": item.content} for item in context.history)
        messages.append({"role": "user", "content": message})
        return messages

    async def _call_llm_node(self, state: AgentGraphState) -> dict[str, str]:
        response = await self.llm_client.ainvoke(state["messages"])
        if not isinstance(response, str) or not response.strip():
            raise ValueError("LLM returned an empty or invalid response")
        return {"response": response}

    def _get_graph(self):
        if self._graph is None:
            graph = StateGraph(AgentGraphState)
            graph.add_node("llm", self._call_llm_node)
            graph.set_entry_point("llm")
            graph.add_edge("llm", END)
            self._graph = graph.compile()
        return self._graph

    async def run(self, message: str, context: AgentContext) -> ChatResponse:
        self.llm_client.ensure_ready()
        messages = self._build_messages(message, context)
        async with asyncio.timeout(self.timeout_seconds):
            result = await self._get_graph().ainvoke({"messages": messages, "response": ""})
        return ChatResponse(
            agent_id=self.agent_id,
            conversation_id=context.conversation_id,
            message=result["response"],
        )

    async def stream(self, message: str, context: AgentContext) -> AsyncIterator[str]:
        self.llm_client.ensure_ready()
        messages = self._build_messages(message, context)
        parts: list[str] = []
        try:
            async with asyncio.timeout(self.timeout_seconds):
                chunks = self.llm_client.astream(messages)
                try:
                    async for chunk in chunks:
                        if not isinstance(chunk, str):
                            raise ValueError("LLM returned an invalid stream chunk")
                        if chunk:
                            parts.append(chunk)
                            yield format_sse("delta", {"content": chunk})
                finally:
                    close = getattr(chunks, "aclose", None)
                    if close is not None:
                        await close()
                full_content = "".join(parts)
                if not full_content.strip():
                    raise ValueError("LLM returned an empty stream")
        except TimeoutError:
            yield format_sse("error", {"code": "llm_timeout"})
            return
        except Exception:
            logger.error("Agent stream failed for agent_id=%s", self.agent_id)
            yield format_sse("error", {"code": "llm_error"})
            return
        yield format_sse("done", {"content": full_content})

    async def respond(self, message: str, context: AgentContext):
        if context.stream_response:
            return self._streaming_response(message, context)
        return await self.run(message, context)

    async def respond_text(self, message: str, context: AgentContext):
        if context.stream_response:
            return self._streaming_response(message, context)
        response = await self.run(message, context)
        return PlainTextResponse(response.message)

    def _streaming_response(self, message: str, context: AgentContext) -> StreamingResponse:
        self.llm_client.ensure_ready()
        return StreamingResponse(
            self.stream(message, context), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
