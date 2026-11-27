from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    agent_id: str = Field(default="default", min_length=1)
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    skill_id: str | None = Field(default=None, alias="skillId")
    system_prompt: str | None = Field(default=None, alias="systemPrompt")
    history: list[ChatMessage] = Field(default_factory=list)
    stream_response: bool = Field(default=False, alias="streamResponse")
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def require_nonblank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value


class AgentContext(BaseModel):
    conversation_id: str | None = None
    skill_id: str | None = None
    system_prompt: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    stream_response: bool = False
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    agent_id: str
    conversation_id: str | None = None
    message: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
