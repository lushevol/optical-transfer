from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class VerifiedChunk:
    session_id: bytes
    chunk_index: int
    total_chunks: int
    data: bytes


class PacketCollector:
    def __init__(self) -> None:
        self._chunks: Dict[Tuple[bytes, int], VerifiedChunk] = {}

    def add_chunk(self, chunk: VerifiedChunk) -> bool:
        key = (chunk.session_id, chunk.chunk_index)
        existing = self._chunks.get(key)
        if existing is not None:
            if existing != chunk:
                raise ValueError("conflicting chunk for session and index")
            return False

        self._chunks[key] = chunk
        return True

    def chunks(self, session_id: Optional[bytes] = None) -> List[VerifiedChunk]:
        collected = self._chunks.values()
        if session_id is not None:
            collected = (chunk for chunk in collected if chunk.session_id == session_id)
        return sorted(collected, key=lambda chunk: (chunk.session_id, chunk.chunk_index))
