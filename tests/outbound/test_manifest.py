from __future__ import annotations

from atlasx.outbound.archive import archive_directory
from atlasx.outbound.manifest import (
    build_manifest,
    manifest_from_json_bytes,
    manifest_to_json_bytes,
)


def test_manifest_contains_archive_hash_and_chunk_metadata(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_text("hello world\n", encoding="utf-8")
    output_path = tmp_path / "payload.tar.gz"

    archive_result = archive_directory(source_dir, output_path)
    manifest = build_manifest(archive_result, chunk_size=4096, total_chunks=7)

    assert manifest.object_type == "single_directory"
    assert manifest.archive_format == "tar.gz"
    assert manifest.archive_byte_length == archive_result.archive_byte_length
    assert manifest.archive_hash == archive_result.archive_hash
    assert manifest.chunk_size == 4096
    assert manifest.total_chunks == 7
    assert manifest.aead_algorithm_id == "aes-256-gcm"
    assert manifest.original_directory_name == "payload"
    assert manifest.fec_parameters is None

    encoded = manifest_to_json_bytes(manifest)
    assert manifest_from_json_bytes(encoded) == manifest
