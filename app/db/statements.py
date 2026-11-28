import re

_INSERT_OR = re.compile(
    "^\\s*INSERT\\s+OR\\s+(REPLACE|IGNORE)\\s+INTO\\s+([A-Za-z_][\\w.]*)\\s*(\\([^)]*\\))?\\s*",
    re.I,
)


def _placeholders(text: str) -> str:
    """'?' → '%s' và '%' → '%%' — bỏ qua phần nằm trong chuỗi '...'."""
    out, quoted = ([], False)
    for ch in text:
        if ch == "'":
            quoted = not quoted
            out.append(ch)
        elif ch == "%":
            out.append("%%")
        elif ch == "?" and (not quoted):
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


def pg(query: str) -> str:
    """'?' → '%s' (dùng cho code gọi psycopg trực tiếp)."""
    return _placeholders(query)
