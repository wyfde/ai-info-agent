from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class SourceItem:
    id: str
    title: str
    source: str
    url: str = ""
    published_at: str = ""
    content: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceItem":
        return cls(
            id=str(value.get("id", "")),
            title=str(value.get("title", "")).strip(),
            source=str(value.get("source", "")).strip(),
            url=str(value.get("url", "")).strip(),
            published_at=str(value.get("published_at", "")).strip(),
            content=str(value.get("content", "")).strip(),
        )
