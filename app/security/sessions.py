import hashlib
import hmac
import re
import time
from .config import SECRET, TTL, PASSWORD


def make_token(*, secret=None) -> str:
    exp = str(int(time.time()) + TTL)
    return (
        exp
        + "."
        + hmac.new(SECRET if secret is None else secret, exp.encode(), hashlib.sha256).hexdigest()
    )


def valid_token(tok: str | None, *, secret=None) -> bool:
    if not tok or not re.fullmatch("[0-9]{1,12}\\.[a-f0-9]{64}", tok):
        return False
    exp, sig = tok.split(".", 1)
    good = hmac.new(SECRET if secret is None else secret, exp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and exp.isdigit() and (int(exp) > time.time())


def check_password(pw: str, *, password=None) -> bool:
    expected = PASSWORD if password is None else password
    return bool(expected) and hmac.compare_digest(pw.encode(), expected.encode())
