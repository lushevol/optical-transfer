from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from atlasx.protocol.header import PacketHeader, encode_header
from atlasx.protocol.constants import PROTOCOL_HEADER_SIZE


PACKET_TYPE_MANIFEST = 0
PACKET_TYPE_DATA = 1


@dataclass(frozen=True)
class SessionPacket:
    header: PacketHeader
    payload: bytes

    def to_bytes(self) -> bytes:
        return build_data_packet(self.header, self.payload)


def build_data_packet(header: PacketHeader, ciphertext: bytes) -> bytes:
    return encode_header(header) + ciphertext


def split_data_packet(packet: bytes) -> Tuple[PacketHeader, bytes]:
    from atlasx.protocol.header import decode_header

    if len(packet) < PROTOCOL_HEADER_SIZE:
        raise ValueError("packet is shorter than the protocol header")

    header = decode_header(packet[:PROTOCOL_HEADER_SIZE])
    payload = packet[PROTOCOL_HEADER_SIZE:]
    if len(payload) != header.payload_length:
        raise ValueError("packet payload length does not match header")
    return header, payload
