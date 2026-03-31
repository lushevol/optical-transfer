from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

PacketType = int
CapabilityFlags = int
ChunkIndex = int
TotalChunks = int
PayloadLength = int
ProtocolVersion = int
KdfId = int
SessionId = bytes
KdfSalt = bytes


@dataclass(frozen=True)
class PacketHeaderFields:
    protocol_version: ProtocolVersion
    capability_flags: CapabilityFlags
    session_id: SessionId
    packet_type: PacketType
    chunk_index: ChunkIndex
    total_chunks: TotalChunks
    payload_length: PayloadLength
    kdf_id: KdfId
    kdf_salt: KdfSalt
    header_crc: Optional[int] = None
