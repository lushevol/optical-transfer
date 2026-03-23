from optical_transfer.protocol.constants import PROTOCOL_HEADER_SIZE
from optical_transfer.protocol.header import PacketHeader, decode_header, encode_header


def test_packet_header_roundtrip_preserves_wire_format() -> None:
    header = PacketHeader(
        protocol_version=1,
        capability_flags=3,
        session_id=b"0123456789abcdef",
        packet_type=2,
        chunk_index=7,
        total_chunks=19,
        payload_length=1536,
        kdf_id=1,
        kdf_salt=b"fedcba9876543210",
    )

    encoded = encode_header(header)

    assert len(encoded) == PROTOCOL_HEADER_SIZE == 59
    assert header.header_crc == 0xA9A789DF
    assert encoded == (
        b"OTV1"
        + b"\x01"
        + b"\x00\x00\x00\x03"
        + b"0123456789abcdef"
        + b"\x02"
        + b"\x00\x00\x00\x07"
        + b"\x00\x00\x00\x13"
        + b"\x00\x00\x06\x00"
        + b"\x01"
        + b"fedcba9876543210"
        + b"\xa9\xa7\x89\xdf"
    )
    assert decode_header(encoded) == header


def test_decode_header_accepts_known_bytes_fixture() -> None:
    raw = (
        b"OTV1"
        + b"\x01"
        + b"\x00\x00\x00\x03"
        + b"0123456789abcdef"
        + b"\x02"
        + b"\x00\x00\x00\x07"
        + b"\x00\x00\x00\x13"
        + b"\x00\x00\x06\x00"
        + b"\x01"
        + b"fedcba9876543210"
        + b"\xa9\xa7\x89\xdf"
    )

    header = decode_header(raw)

    assert header == PacketHeader(
        protocol_version=1,
        capability_flags=3,
        session_id=b"0123456789abcdef",
        packet_type=2,
        chunk_index=7,
        total_chunks=19,
        payload_length=1536,
        kdf_id=1,
        kdf_salt=b"fedcba9876543210",
    )
