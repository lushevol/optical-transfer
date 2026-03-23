from __future__ import annotations

from dataclasses import dataclass

PacketType = int
CapabilityFlags = int
ChunkIndex = int
TotalChunks = int
PayloadLength = int
ProtocolVersion = int
SessionId = bytes


@dataclass(frozen=True, slots=True)
class PacketHeaderFields:
    protocol_version: ProtocolVersion
    capability_flags: CapabilityFlags
    session_id: SessionId
    packet_type: PacketType
    chunk_index: ChunkIndex
    total_chunks: TotalChunks
    payload_length: PayloadLength
