from __future__ import annotations

from dataclasses import dataclass

from optical_transfer.protocol.header import PacketHeader, encode_header


PACKET_TYPE_MANIFEST = 0
PACKET_TYPE_DATA = 1


@dataclass(frozen=True, slots=True)
class SessionPacket:
    header: PacketHeader
    payload: bytes

    def to_bytes(self) -> bytes:
        return build_data_packet(self.header, self.payload)


def build_data_packet(header: PacketHeader, ciphertext: bytes) -> bytes:
    return encode_header(header) + ciphertext


def split_data_packet(packet: bytes) -> tuple[PacketHeader, bytes]:
    from optical_transfer.protocol.constants import PROTOCOL_HEADER_SIZE
    from optical_transfer.protocol.header import decode_header

    header = decode_header(packet[:PROTOCOL_HEADER_SIZE])
    return header, packet[PROTOCOL_HEADER_SIZE:]
