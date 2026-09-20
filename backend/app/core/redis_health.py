"""Process-local circuit breaker; PostgreSQL remains the source of truth."""
import logging
import time
from threading import Lock

import redis
from app.core.config import settings

log = logging.getLogger("recon")


class RedisCircuit:
    def __init__(self):
        self.lock = Lock()
        self.retry_at = 0.0
        self.successes = 0
        self.state = "unknown"
        self.client = None

    def failed(self):
        with self.lock:
            self._failed()

    def _failed(self):
        if self.state != "open":
            log.warning("redis_circuit_open: using PostgreSQL fallback")
        self.state = "open"
        self.successes = 0
        self.retry_at = time.monotonic() + settings.REDIS_PROBE_INTERVAL

    def available(self):
        with self.lock:
            if not settings.REDIS_URL:
                self.state = "disabled"
                self.successes = 0
                self.retry_at = 0.0
                return False
            if time.monotonic() < self.retry_at:
                return self.state == "closed"
            try:
                if self.client is None:
                    self.client = redis.from_url(settings.REDIS_URL,
                        socket_connect_timeout=1, socket_timeout=1, max_connections=5)
                self.client.ping()
            except redis.RedisError:
                self._failed()
                return False
            self.successes += 1
            self.retry_at = time.monotonic() + settings.REDIS_PROBE_INTERVAL
            if self.state == "closed" or self.successes >= settings.REDIS_RECOVERY_PROBES:
                if self.state != "closed":
                    log.info("redis_circuit_closed: Redis recovered")
                self.state = "closed"
                return True
            self.state = "half_open"
            return False


circuit = RedisCircuit()


def publish(task, *args):
    """Best effort notification after a durable queue row has been committed."""
    if not circuit.available():
        return False
    try:
        task.apply_async(args=args, retry=False, ignore_result=True)
        return True
    except Exception:
        # Even ambiguous successful publishes are safe: consumers lock DB rows.
        circuit.failed()
        log.warning("redis_publish_failed: durable work remains queued", exc_info=True)
        return False
