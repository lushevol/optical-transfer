from optical_transfer.protocol.header import PacketHeader, decode_header, encode_header


def test_packet_header_roundtrip_preserves_required_fields() -> None:
    header = PacketHeader(
        protocol_version=1,
        capability_flags=3,
        session_id=b"0123456789abcdef",
        packet_type=2,
        chunk_index=7,
        total_chunks=19,
        payload_length=1536,
    )

    encoded = encode_header(header)
    decoded = decode_header(encoded)

    assert decoded == header
