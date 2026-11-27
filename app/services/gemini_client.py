import asyncio
import json
import os
import time
from uuid import uuid4

from google import genai
from google.genai import errors, types

from .llm_client import LLMNotConfiguredError
from .tool_llm import ModelTurn, ToolCall, ToolMessage, UnconfiguredToolLLMClient
from .gemini_schema import tool_schema
from app.core.config import load_environment


def to_gemini_messages(messages: list[ToolMessage]):
    system, contents, names = [], [], {}
    for message in messages:
        if message.role == "system":
            system.append(message.content)
            continue
        if message.role == "assistant":
            names.update({call.id: call.name for call in message.tool_calls})
            if message.provider_content is not None:
                contents.append(types.Content.model_validate(message.provider_content))
                continue
            parts = [types.Part(text=message.content)] if message.content else []
            parts.extend(types.Part(function_call=types.FunctionCall(id=call.id, name=call.name,
                                                                     args=call.arguments))
                         for call in message.tool_calls)
            contents.append(types.Content(role="model", parts=parts))
        elif message.role == "tool":
            if message.tool_call_id not in names:
                raise ValueError("Tool result does not match a model call")
            part = types.Part(function_response=types.FunctionResponse(
                id=message.tool_call_id, name=names[message.tool_call_id], response=json.loads(message.content),
            ))
            if contents and contents[-1].role == "user":
                contents[-1].parts.append(part)
            else:
                contents.append(types.Content(role="user", parts=[part]))
        else:
            contents.append(types.Content(role="user", parts=[types.Part(text=message.content)]))
    return "\n\n".join(system), contents


class GeminiToolClient:
    def __init__(self, *, api_key: str, model: str, timeout: float = 30.0, min_interval: float = 4.0):
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self.min_interval = min_interval
        self._next_request = 0.0
        self._request_lock = asyncio.Lock()

    def ensure_ready(self):
        if not self._api_key.strip() or not self.model.strip():
            raise LLMNotConfiguredError("Set LLM_API_KEY and LLM_MODEL_NAME")

    async def complete(self, messages: list[ToolMessage], tools: list[dict]) -> ModelTurn:
        self.ensure_ready()
        system, contents = to_gemini_messages(messages)
        declarations = [types.FunctionDeclaration(name=tool["name"], description=tool["description"],
                                                 parameters_json_schema=tool_schema(tool["parameters"])) for tool in tools]
        config = types.GenerateContentConfig(
            system_instruction=system or None, max_output_tokens=4096,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
                if declarations else None,
        )
        async with genai.Client(api_key=self._api_key,
                                http_options=types.HttpOptions(timeout=int(self.timeout * 1000),
                                                               retry_options=types.HttpRetryOptions(attempts=1))).aio as client:
            async with self._request_lock:
                for attempt in range(3):
                    wait = self._next_request - time.monotonic()
                    if wait > 0:
                        await asyncio.sleep(wait)
                    self._next_request = time.monotonic() + self.min_interval
                    try:
                        response = await client.models.generate_content(model=self.model, contents=contents, config=config)
                        break
                    except errors.APIError as error:
                        if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                            raise
                        await asyncio.sleep(2 ** (attempt + 1))
        if not response.candidates or not response.candidates[0].content:
            raise ValueError("Model returned no content")
        candidate = response.candidates[0]
        if candidate.finish_reason not in {None, types.FinishReason.STOP}:
            raise ValueError("Model response is incomplete or blocked")
        content = candidate.content.model_copy(deep=True)
        text, calls = [], []
        for part in content.parts or []:
            if part.function_call is not None:
                call = part.function_call
                call.id = call.id or uuid4().hex
                calls.append(ToolCall(id=call.id, name=call.name, arguments=call.args or {}))
            elif part.text and not part.thought:
                text.append(part.text)
        return ModelTurn(text="".join(text), tool_calls=calls,
                         provider_content=content.model_dump(mode="python", exclude_none=True))

    async def ainvoke(self, messages):
        response = await self.complete([ToolMessage(**message) for message in messages], [])
        return response.text

    async def astream(self, messages):
        yield await self.ainvoke(messages)


def configured_tool_client():
    load_environment()
    key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL_NAME", "").strip()
    if key and model:
        return GeminiToolClient(api_key=key, model=model)
    return UnconfiguredToolLLMClient()
