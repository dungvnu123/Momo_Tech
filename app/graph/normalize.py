import ipaddress
import re
import unicodedata


def phone(value: str) -> str:
    normalized = re.sub(r"[\s.()\-+]", "", value.strip())
    if normalized.startswith("84"):
        normalized = "0" + normalized[2:]
    if not re.fullmatch(r"0\d{9}", normalized):
        raise ValueError("Invalid Vietnamese phone number")
    return normalized


def account(kind: str, bank: str, number: str) -> str:
    if kind == "momo_wallet":
        if bank.strip().upper() not in {"", "MOMO"}:
            raise ValueError("Wallet has inconsistent provider")
        return "account:momo:" + phone(number)
    if kind != "bank":
        raise ValueError(f"Unsupported account type: {kind}")
    bank = bank.strip().upper()
    number = re.sub(r"[\s.\-]", "", number.strip())
    if not bank or bank == "MOMO" or not number.isascii() or not number.isdigit():
        raise ValueError("Bank and numeric account number are required")
    return f"account:bank:{bank}:{number}"


def ip_block(value: str) -> str:
    address = ipaddress.IPv4Address(value)
    return str(ipaddress.IPv4Network(f"{address}/24", strict=False))


def flag(value: str) -> bool:
    if value.lower() in {"true", "1"}:
        return True
    if value.lower() in {"false", "0", ""}:
        return False
    raise ValueError("Invalid boolean value")


def name_match(first: str, second: str) -> bool | None:
    if not first.strip() or not second.strip():
        return None

    def normalize(value):
        value = value.casefold().replace("đ", "d")
        value = "".join(character for character in unicodedata.normalize("NFD", value)
                        if not unicodedata.combining(character))
        return " ".join(value.split())

    return normalize(first) == normalize(second)
