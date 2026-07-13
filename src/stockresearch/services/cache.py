"""In-memory cache with TTL support and size limits.

线程安全说明：
    本模块使用模块级 OrderedDict 作为缓存存储，未加锁。
    在 CPython 下 OrderedDict 的单个操作（get/set/del）因 GIL 而原子，
    但复合操作（如 _sweep_expired 的遍历+删除、get 后 move_to_end）在
    高并发下可能出现竞态（例如两个线程同时淘汰同一 key）。
    对本应用（单进程 FastAPI + 线程池）影响有限：
      - 缓存值是幂等的（重复计算不会产生错误结果，只是浪费一次计算）
      - 最坏情况是缓存项被重复淘汰或短暂重复计算，不会导致数据损坏
    若未来引入多进程或对缓存一致性有更高要求，需改用 threading.Lock
    或迁移到 Redis 等外部缓存。
"""

import json
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_MAX_MEMORY_ENTRIES = 1000
_MAX_FACTORY_ENTRIES = 200

_memory_store: OrderedDict[str, tuple[str, float]] = OrderedDict()
_factory_store: OrderedDict[str, tuple[float, object]] = OrderedDict()

_MEMORY_TTL_SWEEP_INTERVAL = 100
_memory_ops_since_sweep = 0


def _sweep_expired() -> None:
    global _memory_ops_since_sweep
    _memory_ops_since_sweep += 1
    if _memory_ops_since_sweep < _MEMORY_TTL_SWEEP_INTERVAL:
        return
    _memory_ops_since_sweep = 0
    now = time.monotonic()
    expired = [k for k, (_, exp) in _memory_store.items() if exp > 0 and now > exp]
    for k in expired:
        del _memory_store[k]


def _evict_if_full(store: OrderedDict[str, object], max_size: int) -> None:
    while len(store) > max_size:
        store.popitem(last=False)


class CacheService:
    def get(self, key: str) -> str | None:
        entry = _memory_store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at > 0 and time.monotonic() > expires_at:
            del _memory_store[key]
            return None
        _memory_store.move_to_end(key)
        return value

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        expires_at = 0.0
        if ttl_seconds:
            expires_at = time.monotonic() + ttl_seconds
        _memory_store[key] = (value, expires_at)
        _evict_if_full(_memory_store, _MAX_MEMORY_ENTRIES)
        _sweep_expired()

    def get_json(self, key: str) -> dict[str, object] | None:
        raw = self.get(key)
        if raw is None:
            return None
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return None

    def set_json(self, key: str, value: dict[str, object], ttl_seconds: int | None = None) -> None:
        self.set(key, json.dumps(value, ensure_ascii=False), ttl_seconds)

    def clear_memory(self) -> None:
        _memory_store.clear()
        _factory_store.clear()


def get_cached(key: str, ttl_sec: float, factory: Callable[[], T]) -> T:
    now = time.monotonic()
    entry = _factory_store.get(key)
    if entry is not None and now - entry[0] < ttl_sec:
        _factory_store.move_to_end(key)
        return entry[1]  # type: ignore[return-value]
    value = factory()
    _factory_store[key] = (now, value)
    _evict_if_full(_factory_store, _MAX_FACTORY_ENTRIES)
    return value


def peek_cached(key: str, ttl_sec: float) -> T | None:
    """Return a cached factory value without invoking the factory."""
    now = time.monotonic()
    entry = _factory_store.get(key)
    if entry is not None and now - entry[0] < ttl_sec:
        _factory_store.move_to_end(key)
        return entry[1]  # type: ignore[return-value]
    return None


def clear_cache() -> None:
    _memory_store.clear()
    _factory_store.clear()
