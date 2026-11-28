import os
import time
from collections import defaultdict, deque
from fastapi import Request
from .config import LIMITS

_hits: dict = defaultdict(deque)


def client_ip(req: Request, *, behind_proxy=None) -> str:
    fwd = req.headers.get("x-forwarded-for")
    trusted = bool(os.environ.get("THIENLA_BEHIND_PROXY")) if behind_proxy is None else behind_proxy
    return fwd.split(",")[0].strip() if fwd and trusted else req.client.host if req.client else "?"


def rate_limited(req: Request, *, hits=None, behind_proxy=None) -> bool:
    path = req.url.path
    for prefix, n, win in LIMITS:
        if prefix == "/api/ai/pipeline/run" and path != prefix:
            continue
        if prefix in path:
            buckets = _hits if hits is None else hits
            q, now = (buckets[client_ip(req, behind_proxy=behind_proxy), prefix], time.monotonic())
            while q and q[0] < now - win:
                q.popleft()
            if len(q) >= n:
                return True
            q.append(now)
            return False
    return False
