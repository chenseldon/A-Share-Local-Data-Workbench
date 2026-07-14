from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal, Protocol


ConnectorStatus = Literal["fresh", "stale", "failed", "not_collected"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def payload_hash(payload: bytes | str) -> str:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class ConnectorResult:
    source: str
    status: ConnectorStatus
    records: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=utc_now)
    raw_payload_hash: str = ""
    error_message: str | None = None


class DataConnector(Protocol):
    source: str
    module: str

    def fetch(self, *, symbol: str | None = None) -> ConnectorResult:
        """Fetch source data without writing it to the database."""
