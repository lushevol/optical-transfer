from __future__ import annotations

from dataclasses import dataclass

from optical_transfer.protocol.constants import (
    PROTOCOL_HEADER_MAGIC,
    PROTOCOL_HEADER_SIZE,
    PROTOCOL_HEADER_STRUCT,
    PROTOCOL_HEADER_VERSION,
    PROTOCOL_SESSION_ID_SIZE,
)
from optical_transfer.protocol.types import PacketHeaderFields


@dataclass(frozen=True, slots=True)
class PacketHeader(PacketHeaderFields):
    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_HEADER_VERSION:
            raise ValueError(f"unsupported protocol version: {self.protocol_version}")
        if len(self.session_id) != PROTOCOL_SESSION_ID_SIZE:
            raise ValueError("session_id must be 16 bytes")
        if not 0 <= self.capability_flags <= 0xFFFFFFFF:
            raise ValueError("capability_flags out of range")
        if not 0 <= self.packet_type <= 0xFF:
            raise ValueError("packet_type out of range")
        for name in ("chunk_index", "total_chunks", "payload_length"):
            value = getattr(self, name)
            if not 0 <= value <= 0xFFFFFFFF:
                raise ValueError(f"{name} out of range")


def encode_header(header: PacketHeader) -> bytes:
    return PROTOCOL_HEADER_STRUCT.pack(
        PROTOCOL_HEADER_MAGIC,
        header.protocol_version,
        header.capability_flags,
        header.session_id,
        header.packet_type,
        header.chunk_index,
        header.total_chunks,
        header.payload_length,
    )


def decode_header(data: bytes) -> PacketHeader:
    if len(data) != PROTOCOL_HEADER_SIZE:
        raise ValueError(f"header must be exactly {PROTOCOL_HEADER_SIZE} bytes")

    magic, protocol_version, capability_flags, session_id, packet_type, chunk_index, total_chunks, payload_length = PROTOCOL_HEADER_STRUCT.unpack(
        data
    )
    if magic != PROTOCOL_HEADER_MAGIC:
        raise ValueError("invalid header magic")

    return PacketHeader(
        protocol_version=protocol_version,
        capability_flags=capability_flags,
        session_id=session_id,
        packet_type=packet_type,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        payload_length=payload_length,
    )
