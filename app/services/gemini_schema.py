"""Keep tool shapes manageable for Gemini's constrained decoder.

Nested bounded arrays can exceed its state budget. Pydantic still enforces
all limits locally; the provider receives the same fields, types and enums.
"""


def tool_schema(value):
    if isinstance(value, dict):
        return {key: tool_schema(item) for key, item in value.items() if key not in {"maxItems", "minItems"}}
    if isinstance(value, list):
        return [tool_schema(item) for item in value]
    return value
