from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Manifest:
    archive_byte_length: int
    archive_hash: str
    chunk_size: int
    total_chunks: int
    aead_algorithm_id: str
    original_directory_name: str | None = None
