from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_index: int
    data: bytes


def chunk_bytes(data: bytes, chunk_size: int) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not data:
        return []

    return [
        Chunk(chunk_index=chunk_index, data=data[start : start + chunk_size])
        for chunk_index, start in enumerate(range(0, len(data), chunk_size))
    ]
