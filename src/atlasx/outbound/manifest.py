from __future__ import annotations

import json
from dataclasses import asdict

from atlasx.protocol.manifest_types import Manifest
from atlasx.outbound.archive import ArchiveResult


DEFAULT_AEAD_ALGORITHM_ID = "aes-256-gcm"
DEFAULT_OBJECT_TYPE = "single_directory"
DEFAULT_ARCHIVE_FORMAT = "tar.gz"


def build_manifest(
    archive_result: ArchiveResult,
    chunk_size: int,
    total_chunks: int,
) -> Manifest:
    return Manifest(
        object_type=DEFAULT_OBJECT_TYPE,
        archive_format=DEFAULT_ARCHIVE_FORMAT,
        archive_byte_length=archive_result.archive_byte_length,
        archive_hash=archive_result.archive_hash,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        aead_algorithm_id=DEFAULT_AEAD_ALGORITHM_ID,
        fec_parameters=None,
        original_directory_name=archive_result.original_directory_name,
    )


def manifest_to_json_bytes(manifest: Manifest) -> bytes:
    return json.dumps(asdict(manifest), sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_from_json_bytes(data: bytes) -> Manifest:
    payload = json.loads(data.decode("utf-8"))
    return Manifest(**payload)
