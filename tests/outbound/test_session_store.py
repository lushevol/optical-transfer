from __future__ import annotations

from pathlib import Path

import pytest

from atlasx.outbound.session import build_session_payloads, filter_session_payloads
from atlasx.outbound.session_store import load_session_bundle, save_session_bundle, session_bundle_path


def test_save_and_load_session_bundle_preserves_playback_packets(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_bytes(b"x" * 1024)
    payloads = build_session_payloads(source_dir, password="secret", chunk_size=64)

    bundle_path = save_session_bundle(source_dir, payloads)
    loaded = load_session_bundle(source_dir)

    assert bundle_path == session_bundle_path(source_dir)
    assert loaded.session_id == payloads.session_id
    assert loaded.chunk_size == payloads.chunk_size
    assert loaded.total_chunks == payloads.total_chunks
    assert loaded.manifest == payloads.manifest
    assert loaded.manifest_packet == payloads.manifest_packet
    assert loaded.data_packets == payloads.data_packets
    assert loaded.packet_sequence == payloads.packet_sequence


def test_load_session_bundle_requires_existing_bundle(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    with pytest.raises(ValueError, match="full outbound run"):
        load_session_bundle(source_dir)


def test_filter_session_payloads_keeps_only_requested_data_packets(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_bytes(bytes(range(256)) * 32)
    payloads = build_session_payloads(source_dir, password="secret", chunk_size=64)
    missing_indexes = [0, payloads.total_chunks - 1]

    filtered = filter_session_payloads(payloads, missing_indexes)

    assert filtered.session_id == payloads.session_id
    assert filtered.total_chunks == payloads.total_chunks
    assert filtered.manifest_packet == payloads.manifest_packet
    assert filtered.data_packets == [
        payloads.data_packets[missing_indexes[0]],
        payloads.data_packets[missing_indexes[1]],
    ]
    assert filtered.packet_sequence == [payloads.manifest_packet] * 3 + [
        payloads.data_packets[missing_indexes[0]],
        payloads.data_packets[missing_indexes[0]],
        payloads.data_packets[missing_indexes[1]],
        payloads.data_packets[missing_indexes[1]],
    ]


@pytest.mark.parametrize("missing_indexes", [[], [-1], [0, 0], [999]])
def test_filter_session_payloads_rejects_invalid_indexes(tmp_path: Path, missing_indexes: list[int]) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")
    payloads = build_session_payloads(source_dir, password="secret", chunk_size=32)

    with pytest.raises(ValueError):
        filter_session_payloads(payloads, missing_indexes)
