from __future__ import annotations

from optical_transfer.protocol.header import PacketHeader, encode_header
from optical_transfer.sender.packets import build_data_packet


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
