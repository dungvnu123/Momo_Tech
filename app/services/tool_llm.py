from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .llm_client import LLMClient, UnconfiguredLLMClient


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    arguments: dict[str, JsonValue]


class ModelTurn(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    provider_content: dict | None = None


class ToolMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    provider_content: dict | None = None


class ToolLLMClient(LLMClient, Protocol):
    async def complete(self, messages: list[ToolMessage], tools: list[dict]) -> ModelTurn:
        raise NotImplementedError


class UnconfiguredToolLLMClient(UnconfiguredLLMClient):
    async def complete(self, messages: list[ToolMessage], tools: list[dict]) -> ModelTurn:
        self.ensure_ready()
