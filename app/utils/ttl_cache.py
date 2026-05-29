import time
from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class TTLCache(Generic[T]):
    ttl_seconds: int
    _store: dict[str, tuple[float, T]] = field(default_factory=dict)

    def get(self, key: str) -> T | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.time() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: T) -> None:
        self._store[key] = (time.time() + self.ttl_seconds, value)

