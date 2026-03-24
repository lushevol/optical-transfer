from __future__ import annotations

from optical_transfer.protocol.header import PacketHeader, encode_header
from optical_transfer.sender.packets import build_data_packet
from optical_transfer.sender.session import build_session_payloads


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


def test_repeated_session_builds_do_not_reuse_identical_packet_bytes(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_text("hello world\n", encoding="utf-8")

    first = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)
    second = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)

    assert first.packet_payloads != second.packet_payloads
