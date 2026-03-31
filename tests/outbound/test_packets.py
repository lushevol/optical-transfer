from __future__ import annotations

import pytest

from atlasx.protocol.header import PacketHeader, encode_header
from atlasx.outbound.packets import build_data_packet, split_data_packet
from atlasx.outbound.session import build_session_payloads


def test_build_data_packet_wraps_header_and_ciphertext() -> None:
    header = PacketHeader(
        protocol_version=1,
        capability_flags=0,
        session_id=b"0123456789abcdef",
        packet_type=1,
        chunk_index=4,
        total_chunks=8,
        payload_length=16,
        kdf_id=1,
        kdf_salt=b"fedcba9876543210",
    )
    ciphertext = b"ciphertext-bytes"

    assert build_data_packet(header, ciphertext) == encode_header(header) + ciphertext


def test_split_data_packet_rejects_header_payload_length_tampering() -> None:
    header = PacketHeader(
        protocol_version=1,
        capability_flags=0,
        session_id=b"0123456789abcdef",
        packet_type=1,
        chunk_index=4,
        total_chunks=8,
        payload_length=16,
        kdf_id=1,
        kdf_salt=b"fedcba9876543210",
    )
    packet = build_data_packet(header, b"ciphertext-bytes")
    tampered_header = PacketHeader(
        protocol_version=header.protocol_version,
        capability_flags=header.capability_flags,
        session_id=header.session_id,
        packet_type=header.packet_type,
        chunk_index=header.chunk_index,
        total_chunks=header.total_chunks,
        payload_length=15,
        kdf_id=header.kdf_id,
        kdf_salt=header.kdf_salt,
    )
    tampered_packet = encode_header(tampered_header) + b"ciphertext-bytes"

    with pytest.raises(ValueError):
        split_data_packet(tampered_packet)


def test_repeated_session_builds_do_not_reuse_identical_packet_bytes(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_text("hello world\n", encoding="utf-8")

    first = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)
    second = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)

    assert first.packet_payloads != second.packet_payloads


def test_build_session_payloads_removes_temporary_archive(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_text("hello world\n", encoding="utf-8")

    session = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)

    assert session.archive_result.archive_path.exists() is False
    assert session.archive_bytes.startswith(b"\x1f\x8b")


def test_packet_sequence_repeats_data_packets_for_capture_resilience(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_bytes(b"x" * 4096)

    session = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)

    data_occurrences = [session.packet_payloads.count(packet) for packet in session.data_packets]

    assert session.packet_payloads.count(session.manifest_packet) == 3
    assert data_occurrences
    assert set(data_occurrences) == {2}
