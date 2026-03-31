from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Manifest:
    object_type: str
    archive_format: str
    archive_byte_length: int
    archive_hash: str
    chunk_size: int
    total_chunks: int
    aead_algorithm_id: str
    fec_parameters: Optional[Dict[str, Optional[int]]] = None
    original_directory_name: Optional[str] = None
