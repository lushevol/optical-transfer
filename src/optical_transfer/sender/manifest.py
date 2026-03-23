from __future__ import annotations

import json
from dataclasses import asdict

from optical_transfer.protocol.manifest_types import Manifest
from optical_transfer.sender.archive import ArchiveResult


DEFAULT_AEAD_ALGORITHM_ID = "aes-256-gcm"


def build_manifest(
    archive_result: ArchiveResult,
    chunk_size: int,
    total_chunks: int,
) -> Manifest:
    return Manifest(
        archive_byte_length=archive_result.archive_byte_length,
        archive_hash=archive_result.archive_hash,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        aead_algorithm_id=DEFAULT_AEAD_ALGORITHM_ID,
        original_directory_name=archive_result.original_directory_name,
    )


def manifest_to_json_bytes(manifest: Manifest) -> bytes:
    return json.dumps(asdict(manifest), sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_from_json_bytes(data: bytes) -> Manifest:
    payload = json.loads(data.decode("utf-8"))
    return Manifest(**payload)
