import hashlib
import hmac
import time
from .config import SECRET, KHACH_TTL


def hash_pin(pin: str, salt: bytes) -> bytes:
    return hashlib.scrypt(pin.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


def check_pin(pin: str, salt: bytes, digest: bytes) -> bool:
    return hmac.compare_digest(hash_pin(pin, bytes(salt)), bytes(digest))


def make_khach_token(phone: str) -> str:
    body = f"{phone}.{int(time.time()) + KHACH_TTL}"
    return body + "." + hmac.new(SECRET, b"khach:" + body.encode(), hashlib.sha256).hexdigest()


def khach_phone(tok: str | None) -> str | None:
    """Trả SĐT nếu phiên khách hợp lệ, ngược lại None."""
    try:
        phone, exp, sig = (tok or "").split(".")
    except ValueError:
        return None
    good = hmac.new(SECRET, f"khach:{phone}.{exp}".encode(), hashlib.sha256).hexdigest()
    return (
        phone
        if hmac.compare_digest(sig, good) and exp.isdigit() and (int(exp) > time.time())
        else None
    )
