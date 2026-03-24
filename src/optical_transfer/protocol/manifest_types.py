from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Manifest:
    object_type: str
    archive_format: str
    archive_byte_length: int
    archive_hash: str
    chunk_size: int
    total_chunks: int
    aead_algorithm_id: str
    fec_parameters: dict[str, int | None] | None = None
    original_directory_name: str | None = None
