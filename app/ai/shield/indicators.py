import re
import unicodedata
from urllib.parse import urlsplit

from app.graph.normalize import account, phone

BANKS = {
    "ACB": ("acb", "a chau"), "TCB": ("tcb", "techcombank"),
    "VCB": ("vcb", "vietcombank"), "MBB": ("mbb", "mb", "mbbank"),
    "VPB": ("vpb", "vpbank"), "BIDV": ("bidv",), "CTG": ("ctg", "vietinbank"),
    "TPB": ("tpb", "tpbank"), "STB": ("stb", "sacombank"), "VIB": ("vib",),
}


def _plain(value):
    value = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return " ".join("".join(char for char in value if not unicodedata.combining(char)).split())


def bank_code(value):
    normalized = _plain(value or "")
    return next((code for code, aliases in BANKS.items() if normalized in aliases), (value or "").upper())


def canonical_indicator(indicator) -> str:
    raw = indicator.raw.strip()
    if indicator.kind in {"bank_account", "wallet", "phone"}:
        candidates = re.findall(r"(?<!\w)\+?[0-9oO](?:[0-9oO\s.\-]*[0-9oO])?(?!\w)", raw)
        candidates = [value for value in candidates if re.search(r"\d", value)
                      and 6 <= len(re.sub(r"[^0-9oO]", "", value)) <= 20]
        if len(candidates) != 1:
            raise ValueError("Indicator must contain exactly one numeric identifier")
        raw = candidates[0].replace("o", "0").replace("O", "0")
        if indicator.kind == "bank_account":
            return account("bank", bank_code(indicator.bank), raw)
        if indicator.kind == "wallet":
            return account("momo_wallet", "MoMo", raw)
        return "phone:" + phone(raw)
    parsed = urlsplit(raw if "://" in raw else "https://" + raw)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not host or "." not in host or parsed.username or parsed.password:
        raise ValueError("Invalid URL indicator")
    if host in {"bit.ly", "tinyurl.com", "t.co"}:
        return "url:" + host + parsed.path
    return "domain:" + host


def validate_report(result, text):
    for index, indicator in enumerate(result.indicators):
        if indicator.raw.casefold() not in text.casefold():
            raise ValueError(f"Indicator {index}: raw must be a literal source substring, not normalized digits")
        try:
            canonical_indicator(indicator)
        except ValueError:
            raise ValueError(f"Indicator {index}: invalid account/phone/URL; choose the correct type and copy only its source value") from None
        if indicator.kind == "bank_account":
            aliases = BANKS.get(bank_code(indicator.bank), (_plain(indicator.bank or ""),))
            if not any(alias and re.search(r"\b" + re.escape(alias) + r"\b", _plain(text)) for alias in aliases):
                raise ValueError(f"Indicator {index}: bank name/code must also be present in the source text")


def redact_text(text: str) -> str:
    def replace(match):
        digits = "".join(character for character in match.group() if character.isdigit())
        return digits[:2] + "****" + digits[-2:]
    return re.sub(r"(?<!\w)(?:\+?\d[\s.\-]*){7,}(?!\w)", replace, text)
