from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')

    evidence_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str | None = None
    request_id: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    tool_output: dict[str, Any] = Field(default_factory=dict)
    model_name: str | None = None
    model_version: str | None = None
    kind: str = 'tool'
    status: str = 'recorded'


class EvidenceStore:
    def __init__(self) -> None:
        self._items: dict[str, EvidenceEntry] = {}

    def add(self, *, evidence_id: str | None = None, **kwargs: Any) -> EvidenceEntry:
        item = EvidenceEntry(evidence_id=evidence_id or f"ev-{len(self._items) + 1}", **kwargs)
        self._items[item.evidence_id] = item
        return item

    def get(self, evidence_id: str) -> EvidenceEntry | None:
        return self._items.get(evidence_id)

    def list(self) -> list[EvidenceEntry]:
        return list(self._items.values())


evidence_store = EvidenceStore()
