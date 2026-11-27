from collections.abc import AsyncIterator, Sequence
from typing import Literal, NoReturn, Protocol, TypedDict


class LLMMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMNotConfiguredError(RuntimeError):
    pass


class LLMClient(Protocol):
    def ensure_ready(self) -> None: ...

    async def ainvoke(self, messages: Sequence[LLMMessage]) -> str: ...

    def astream(self, messages: Sequence[LLMMessage]) -> AsyncIterator[str]: ...


class UnconfiguredLLMClient:
    def ensure_ready(self) -> NoReturn:
        raise LLMNotConfiguredError("LLM client is not configured")

    async def ainvoke(self, messages: Sequence[LLMMessage]) -> str:
        self.ensure_ready()

    def astream(self, messages: Sequence[LLMMessage]) -> AsyncIterator[str]:
        self.ensure_ready()
