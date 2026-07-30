from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from atlasx.protocol.header import PacketHeader
from atlasx.protocol.manifest_types import Manifest
from atlasx.protocol.constants import PROTOCOL_HEADER_VERSION, PROTOCOL_KDF_SALT_SIZE
from atlasx.foo.archive import ArchiveResult
from atlasx.foo.bundle import BUNDLE_FORMAT, build_bundle_chunks, bundle_stream_bytes
from atlasx.foo.crypto import ChunkCryptoSession
from atlasx.foo.manifest import build_manifest, manifest_to_json_bytes
from atlasx.foo.packets import PACKET_TYPE_DATA, PACKET_TYPE_MANIFEST, build_data_packet


_AEAD_NONCE_SIZE = 12
_KDF_ID = 1
_MANIFEST_REPEAT_COUNT = 3
_DATA_PACKET_REPEAT_COUNT = 2


@dataclass(frozen=True)
class SessionPayloadSet:
    session_id: bytes
    archive_result: ArchiveResult
    archive_bytes: bytes
    manifest: Manifest
    crypto_session: ChunkCryptoSession
    kdf_salt: bytes
    chunk_size: int
    total_chunks: int
    manifest_packet: bytes
    data_packets: List[bytes]

    @property
    def packet_payloads(self) -> List[bytes]:
        repeated_data_packets = [
            packet
            for packet in self.data_packets
            for _ in range(_DATA_PACKET_REPEAT_COUNT)
        ]
        return [self.manifest_packet] * _MANIFEST_REPEAT_COUNT + repeated_data_packets

    @property
    def packet_sequence(self) -> List[bytes]:
        return self.packet_payloads

    @property
    def packets(self) -> List[bytes]:
        return self.packet_payloads


def filter_session_payloads(payloads: SessionPayloadSet, missing_indexes: list[int]) -> SessionPayloadSet:
    if not missing_indexes:
        raise ValueError("missing chunk indexes must not be empty")
    if len(set(missing_indexes)) != len(missing_indexes):
        raise ValueError("missing chunk indexes must not contain duplicates")

    invalid_indexes = [
        index
        for index in missing_indexes
        if index < 0 or index >= payloads.total_chunks
    ]
    if invalid_indexes:
        raise ValueError(
            "missing chunk indexes are outside the session range: "
            f"{invalid_indexes}"
        )

    return SessionPayloadSet(
        session_id=payloads.session_id,
        archive_result=payloads.archive_result,
        archive_bytes=payloads.archive_bytes,
        manifest=payloads.manifest,
        crypto_session=payloads.crypto_session,
        kdf_salt=payloads.kdf_salt,
        chunk_size=payloads.chunk_size,
        total_chunks=payloads.total_chunks,
        manifest_packet=payloads.manifest_packet,
        data_packets=[payloads.data_packets[index] for index in missing_indexes],
    )


def build_session_payloads(source_dir: Path, password: str, chunk_size: int) -> SessionPayloadSet:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    source_dir = Path(source_dir)
    chunks = build_bundle_chunks(source_dir, chunk_size)
    archive_bytes = bundle_stream_bytes(chunk.data for chunk in chunks)
    archive_result = ArchiveResult(
        archive_path=source_dir.parent / f".{source_dir.name}-{secrets.token_hex(8)}.atlasx-bundle",
        archive_byte_length=len(archive_bytes),
        archive_hash=hashlib.sha256(archive_bytes).hexdigest(),
        original_directory_name=source_dir.name,
    )
    manifest = build_manifest(
        archive_result,
        chunk_size=chunk_size,
        total_chunks=len(chunks),
        archive_format=BUNDLE_FORMAT,
    )

    session_id = _derive_session_id()
    kdf_salt = _derive_kdf_salt()
    crypto_session = ChunkCryptoSession(password=password, salt=kdf_salt)

    manifest_packet = _build_manifest_packet(
        manifest=manifest,
        crypto_session=crypto_session,
        session_id=session_id,
        total_chunks=len(chunks),
        kdf_salt=kdf_salt,
    )
    data_packets = [
        _build_data_packet(
            chunk_index=chunk.chunk_index,
            chunk_data=chunk.data,
            crypto_session=crypto_session,
            session_id=session_id,
            total_chunks=len(chunks),
            kdf_salt=kdf_salt,
        )
        for chunk in chunks
    ]

    return SessionPayloadSet(
        session_id=session_id,
        archive_result=archive_result,
        archive_bytes=archive_bytes,
        manifest=manifest,
        crypto_session=crypto_session,
        kdf_salt=kdf_salt,
        chunk_size=chunk_size,
        total_chunks=len(chunks),
        manifest_packet=manifest_packet,
        data_packets=data_packets,
    )


def _build_manifest_packet(
    manifest: Manifest,
    crypto_session: ChunkCryptoSession,
    session_id: bytes,
    total_chunks: int,
    kdf_salt: bytes,
) -> bytes:
    manifest_payload = manifest_to_json_bytes(manifest)
    encrypted_blob = _encrypt_payload(
        payload=manifest_payload,
        crypto_session=crypto_session,
        session_id=session_id,
        packet_type=PACKET_TYPE_MANIFEST,
        chunk_index=0,
        total_chunks=total_chunks,
        payload_length=len(manifest_payload) + _AEAD_NONCE_SIZE + 16,
        kdf_salt=kdf_salt,
    )
    header = PacketHeader(
        protocol_version=PROTOCOL_HEADER_VERSION,
        capability_flags=0,
        session_id=session_id,
        packet_type=PACKET_TYPE_MANIFEST,
        chunk_index=0,
        total_chunks=total_chunks,
        payload_length=len(encrypted_blob),
        kdf_id=_KDF_ID,
        kdf_salt=kdf_salt,
    )
    return build_data_packet(header, encrypted_blob)


def _build_data_packet(
    chunk_index: int,
    chunk_data: bytes,
    crypto_session: ChunkCryptoSession,
    session_id: bytes,
    total_chunks: int,
    kdf_salt: bytes,
) -> bytes:
    encrypted_blob = _encrypt_payload(
        payload=chunk_data,
        crypto_session=crypto_session,
        session_id=session_id,
        packet_type=PACKET_TYPE_DATA,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        payload_length=len(chunk_data) + _AEAD_NONCE_SIZE + 16,
        kdf_salt=kdf_salt,
    )
    header = PacketHeader(
        protocol_version=PROTOCOL_HEADER_VERSION,
        capability_flags=0,
        session_id=session_id,
        packet_type=PACKET_TYPE_DATA,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        payload_length=len(encrypted_blob),
        kdf_id=_KDF_ID,
        kdf_salt=kdf_salt,
    )
    return build_data_packet(header, encrypted_blob)


def _encrypt_payload(
    payload: bytes,
    crypto_session: ChunkCryptoSession,
    session_id: bytes,
    packet_type: int,
    chunk_index: int,
    total_chunks: int,
    payload_length: int,
    kdf_salt: bytes,
) -> bytes:
    nonce = _derive_nonce()
    aead = AESGCM(crypto_session.key())
    ciphertext = aead.encrypt(
        nonce,
        payload,
        _associated_data(
            session_id=session_id,
            packet_type=packet_type,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            payload_length=payload_length,
            kdf_salt=kdf_salt,
        ),
    )
    return nonce + ciphertext


def _derive_nonce() -> bytes:
    return secrets.token_bytes(_AEAD_NONCE_SIZE)


def _associated_data(
    *,
    session_id: bytes,
    packet_type: int,
    chunk_index: int,
    total_chunks: int,
    payload_length: int,
    kdf_salt: bytes,
) -> bytes:
    return b"|".join(
        [
            session_id,
            packet_type.to_bytes(1, "big", signed=False),
            chunk_index.to_bytes(8, "big", signed=False),
            total_chunks.to_bytes(4, "big", signed=False),
            payload_length.to_bytes(4, "big", signed=False),
            kdf_salt,
        ]
    )


def _derive_session_id() -> bytes:
    return secrets.token_bytes(16)


def _derive_kdf_salt() -> bytes:
    return secrets.token_bytes(PROTOCOL_KDF_SALT_SIZE)
