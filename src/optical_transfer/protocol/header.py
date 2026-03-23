from __future__ import annotations

from binascii import crc32
from dataclasses import dataclass

from optical_transfer.protocol.constants import (
    PROTOCOL_HEADER_MAGIC,
    PROTOCOL_HEADER_BODY_SIZE,
    PROTOCOL_HEADER_BODY_STRUCT,
    PROTOCOL_HEADER_SIZE,
    PROTOCOL_HEADER_STRUCT,
    PROTOCOL_HEADER_VERSION,
    PROTOCOL_KDF_SALT_SIZE,
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
        if len(self.kdf_salt) != PROTOCOL_KDF_SALT_SIZE:
            raise ValueError("kdf_salt must be 16 bytes")
        if not 0 <= self.capability_flags <= 0xFFFFFFFF:
            raise ValueError("capability_flags out of range")
        if not 0 <= self.packet_type <= 0xFF:
            raise ValueError("packet_type out of range")
        if not 0 <= self.kdf_id <= 0xFF:
            raise ValueError("kdf_id out of range")
        for name in ("chunk_index", "total_chunks", "payload_length"):
            value = getattr(self, name)
            if not 0 <= value <= 0xFFFFFFFF:
                raise ValueError(f"{name} out of range")
        computed_header_crc = _compute_header_crc(self)
        if self.header_crc is None:
            object.__setattr__(self, "header_crc", computed_header_crc)
        elif self.header_crc != computed_header_crc:
            raise ValueError("header_crc does not match encoded header")
        if not 0 <= self.header_crc <= 0xFFFFFFFF:
            raise ValueError("header_crc out of range")


def encode_header(header: PacketHeader) -> bytes:
    encoded_body = PROTOCOL_HEADER_BODY_STRUCT.pack(
        PROTOCOL_HEADER_MAGIC,
        header.protocol_version,
        header.capability_flags,
        header.session_id,
        header.packet_type,
        header.chunk_index,
        header.total_chunks,
        header.payload_length,
        header.kdf_id,
        header.kdf_salt,
    )
    header_crc = _compute_header_crc(header)
    if header.header_crc != header_crc:
        raise ValueError("header_crc does not match encoded header")
    return encoded_body + header_crc.to_bytes(4, "big")


def decode_header(data: bytes) -> PacketHeader:
    if len(data) != PROTOCOL_HEADER_SIZE:
        raise ValueError(f"header must be exactly {PROTOCOL_HEADER_SIZE} bytes")

    magic, protocol_version, capability_flags, session_id, packet_type, chunk_index, total_chunks, payload_length, kdf_id, kdf_salt, header_crc = PROTOCOL_HEADER_STRUCT.unpack(
        data
    )
    if magic != PROTOCOL_HEADER_MAGIC:
        raise ValueError("invalid header magic")
    if header_crc != _compute_header_crc_from_bytes(data[:PROTOCOL_HEADER_BODY_SIZE]):
        raise ValueError("invalid header crc")

    return PacketHeader(
        protocol_version=protocol_version,
        capability_flags=capability_flags,
        session_id=session_id,
        packet_type=packet_type,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        payload_length=payload_length,
        kdf_id=kdf_id,
        kdf_salt=kdf_salt,
        header_crc=header_crc,
    )


def _compute_header_crc(header: PacketHeader) -> int:
    body = PROTOCOL_HEADER_BODY_STRUCT.pack(
        PROTOCOL_HEADER_MAGIC,
        header.protocol_version,
        header.capability_flags,
        header.session_id,
        header.packet_type,
        header.chunk_index,
        header.total_chunks,
        header.payload_length,
        header.kdf_id,
        header.kdf_salt,
    )
    return _compute_header_crc_from_bytes(body)


def _compute_header_crc_from_bytes(body: bytes) -> int:
    return crc32(body) & 0xFFFFFFFF
