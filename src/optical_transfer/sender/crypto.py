from __future__ import annotations

from dataclasses import dataclass
import hashlib
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from optical_transfer.sender.chunker import Chunk


_KEY_LENGTH = 32
_NONCE_LENGTH = 12
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


@dataclass(frozen=True, slots=True)
class EncryptedChunk:
    chunk_index: int
    nonce: bytes
    ciphertext: bytes

    def with_ciphertext(self, ciphertext: bytes) -> "EncryptedChunk":
        return EncryptedChunk(
            chunk_index=self.chunk_index,
            nonce=self.nonce,
            ciphertext=ciphertext,
        )

    def with_nonce(self, nonce: bytes) -> "EncryptedChunk":
        return EncryptedChunk(
            chunk_index=self.chunk_index,
            nonce=nonce,
            ciphertext=self.ciphertext,
        )


def encrypt_chunk(chunk: Chunk, password: str, session_id: bytes, salt: bytes) -> EncryptedChunk:
    key = _derive_key(password=password, salt=salt)
    nonce = _derive_nonce(session_id=session_id, chunk_index=chunk.chunk_index)
    aead = AESGCM(key)
    ciphertext = aead.encrypt(nonce, chunk.data, _associated_data(session_id, chunk.chunk_index))
    return EncryptedChunk(chunk_index=chunk.chunk_index, nonce=nonce, ciphertext=ciphertext)


def decrypt_chunk(
    encrypted_chunk: EncryptedChunk,
    password: str,
    session_id: bytes,
    salt: bytes,
) -> Chunk:
    key = _derive_key(password=password, salt=salt)
    aead = AESGCM(key)
    plaintext = aead.decrypt(
        encrypted_chunk.nonce,
        encrypted_chunk.ciphertext,
        _associated_data(session_id, encrypted_chunk.chunk_index),
    )
    return Chunk(chunk_index=encrypted_chunk.chunk_index, data=plaintext)


@lru_cache(maxsize=128)
def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LENGTH,
    )


def _derive_nonce(session_id: bytes, chunk_index: int) -> bytes:
    if chunk_index < 0:
        raise ValueError("chunk_index must be non-negative")
    digest = hashlib.sha256(session_id + chunk_index.to_bytes(8, "big", signed=False)).digest()
    return digest[:_NONCE_LENGTH]


def _associated_data(session_id: bytes, chunk_index: int) -> bytes:
    return session_id + chunk_index.to_bytes(8, "big", signed=False)
