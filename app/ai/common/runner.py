import asyncio
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from app import db
from app.services.tool_llm import ToolMessage


class AIOutputError(RuntimeError):
    pass


class StructuredRunner:
    def __init__(self, client, *, cache_path=None, timeout=30.0):
        self.client, self.timeout = client, timeout
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache_hits = self.model_calls = 0
        self._db = None
        if self.cache_path:   # PostgreSQL: 1 kết nối tự commit cho cả runner (schema theo đường dẫn cache — xem app/db.py)
            self._db = db.connect(self.cache_path, autocommit=True)
            self._db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def _cached(self, key):
        if self._db:
            row = self._db.execute("SELECT payload FROM responses WHERE key = ?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

    async def run(self, name, prompt, payload, output_type, validate):
        schema = output_type.model_json_schema()
        identity = {"provider": type(self.client).__name__, "model": getattr(self.client, "model", "test"),
                    "tool": name, "prompt": prompt, "input": payload, "schema": schema}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        cached = self._cached(key)
        if cached is not None:
            try:
                result = output_type.model_validate(cached)
                validate(result)
            except (ValidationError, ValueError):
                self._db.execute("DELETE FROM responses WHERE key=?", (key,))
            else:
                self.cache_hits += 1
                return result
        self.client.ensure_ready()
        messages = [ToolMessage(role="system", content=prompt),
                    ToolMessage(role="user", content=json.dumps(payload, ensure_ascii=False))]
        definition = {"name": name, "description": "Return the requested structured analysis only", "parameters": schema}
        for attempt in range(2):
            self.model_calls += 1
            response = await asyncio.wait_for(self.client.complete(messages, [definition]), self.timeout)
            if len(response.tool_calls) != 1 or response.tool_calls[0].name != name:
                raise AIOutputError("Model did not return the required output tool")
            call = response.tool_calls[0]
            try:
                result = output_type.model_validate(call.arguments)
                validate(result)
            except (ValidationError, ValueError) as error:
                if attempt:
                    raise AIOutputError("Model output failed schema or grounding validation") from None
                messages.extend([
                    ToolMessage(role="assistant", tool_calls=response.tool_calls, provider_content=response.provider_content),
                    ToolMessage(role="tool", tool_call_id=call.id,
                                content=json.dumps({"ok": False,
                                    "error": "Use exact source spans and complete input IDs. Omit an indicator if its literal source cannot be extracted.",
                                    "fields": [{"field": ".".join(map(str, item["loc"])), "code": item["type"]}
                                               for item in error.errors(include_input=False, include_url=False)]
                                               if isinstance(error, ValidationError) else [],
                                    "grounding_error": str(error) if not isinstance(error, ValidationError) else None})),
                ])
                continue
            if self._db:
                self._db.execute("INSERT OR REPLACE INTO responses VALUES (?, ?)", (key, result.model_dump_json()))
            return result
