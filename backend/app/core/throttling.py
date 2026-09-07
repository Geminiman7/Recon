"""Atomic expiring Redis buckets; fail closed if production Redis is unavailable."""
import hashlib
import time
from collections import OrderedDict
from threading import Lock
from functools import lru_cache
import redis
from fastapi import HTTPException
from app.core.config import settings

SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""
_local = OrderedDict()
_lock = Lock()


@lru_cache(maxsize=1)
def client():
    return redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2, max_connections=5)


def throttle(scope: str, identity: str, limit: int, window: int = 60):
    digest = hashlib.sha256(identity.encode()).hexdigest()
    key = f"recon:rate:{scope}:{digest}:{int(time.time()) // window}"
    if settings.REDIS_URL:
        try:
            count = client().eval(SCRIPT, 1, key, window)
        except redis.RedisError as exc:
            raise HTTPException(503, "Sign-in is temporarily unavailable.", headers={"Retry-After": "30"}) from exc
    elif settings.is_production:
        raise HTTPException(503, "Sign-in is temporarily unavailable.")
    else:
        with _lock:
            now = time.monotonic()
            for old_key in list(_local):
                if _local[old_key][1] <= now:
                    del _local[old_key]
            if key not in _local and len(_local) >= 10000:
                _local.popitem(last=False)
            count = _local.get(key, (0, 0))[0] + 1
            _local[key] = (count, now + window)
    if count > limit:
        raise HTTPException(429, "Too many attempts. Try again later.", headers={"Retry-After": str(window)})
