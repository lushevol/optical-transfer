from __future__ import annotations

import tempfile
import secrets
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from optical_transfer.protocol.header import PacketHeader
from optical_transfer.protocol.manifest_types import Manifest
from optical_transfer.protocol.constants import PROTOCOL_HEADER_VERSION, PROTOCOL_KDF_SALT_SIZE
from optical_transfer.sender.archive import ArchiveResult, archive_directory
from optical_transfer.sender.chunker import chunk_bytes
from optical_transfer.sender.crypto import ChunkCryptoSession
from optical_transfer.sender.manifest import build_manifest, manifest_to_json_bytes
from optical_transfer.sender.packets import PACKET_TYPE_DATA, PACKET_TYPE_MANIFEST, build_data_packet


_AEAD_NONCE_SIZE = 12
_KDF_ID = 1


@dataclass(frozen=True, slots=True)
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
    data_packets: list[bytes]

    @property
    def packet_payloads(self) -> list[bytes]:
        return [self.manifest_packet, *self.data_packets]

    @property
    def packet_sequence(self) -> list[bytes]:
        return self.packet_payloads

    @property
    def packets(self) -> list[bytes]:
        return self.packet_payloads


def build_session_payloads(source_dir: Path, password: str, chunk_size: int) -> SessionPayloadSet:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    archive_result = _archive_to_temporary_path(Path(source_dir))
    archive_bytes = archive_result.archive_path.read_bytes()
    try:
        chunks = chunk_bytes(archive_bytes, chunk_size)
        manifest = build_manifest(archive_result, chunk_size=chunk_size, total_chunks=len(chunks))

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
    finally:
        archive_result.archive_path.unlink(missing_ok=True)

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


def _archive_to_temporary_path(source_dir: Path) -> ArchiveResult:
    with tempfile.NamedTemporaryFile(prefix=f"{source_dir.name}-", suffix=".tar.gz", delete=False, dir=source_dir.parent) as handle:
        output_path = Path(handle.name)
    return archive_directory(source_dir, output_path)
