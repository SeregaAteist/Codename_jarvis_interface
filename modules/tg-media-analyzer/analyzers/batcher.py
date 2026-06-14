"""Smart media batcher — groups items by content type and size."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class MediaBatch:
    items: list[dict] = field(default_factory=list)
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def photos(self) -> list[dict]:
        return [i for i in self.items if i["type"] == "photo"]

    @property
    def videos(self) -> list[dict]:
        return [i for i in self.items if i["type"] in ("video", "voice", "video_note")]


def smart_batch(items: list[dict], max_size: int = 5) -> list[MediaBatch]:
    """
    Groups media items into batches.
    Strategy: chunks of max_size. Future: semantic/visual clustering.
    """
    batches = []
    for i in range(0, len(items), max_size):
        batches.append(MediaBatch(items=items[i : i + max_size]))
    return batches
