from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import secrets

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


@dataclass(frozen=True, slots=True)
class ChunkCryptoSession:
    password: str
    salt: bytes
    _key: bytes | None = field(default=None, init=False, repr=False, compare=False, hash=False)

    def key(self) -> bytes:
        if self._key is None:
            object.__setattr__(self, "_key", _derive_key(self.password, self.salt))
        return self._key

    def clear(self) -> None:
        object.__setattr__(self, "_key", None)


def encrypt_chunk(chunk: Chunk, crypto_session: ChunkCryptoSession, session_id: bytes) -> EncryptedChunk:
    key = crypto_session.key()
    nonce = secrets.token_bytes(_NONCE_LENGTH)
    aead = AESGCM(key)
    ciphertext = aead.encrypt(nonce, chunk.data, _associated_data(session_id, chunk.chunk_index))
    return EncryptedChunk(chunk_index=chunk.chunk_index, nonce=nonce, ciphertext=ciphertext)


def decrypt_chunk(
    encrypted_chunk: EncryptedChunk,
    crypto_session: ChunkCryptoSession,
    session_id: bytes,
) -> Chunk:
    key = crypto_session.key()
    aead = AESGCM(key)
    plaintext = aead.decrypt(
        encrypted_chunk.nonce,
        encrypted_chunk.ciphertext,
        _associated_data(session_id, encrypted_chunk.chunk_index),
    )
    return Chunk(chunk_index=encrypted_chunk.chunk_index, data=plaintext)


def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LENGTH,
    )


def _associated_data(session_id: bytes, chunk_index: int) -> bytes:
    return session_id + chunk_index.to_bytes(8, "big", signed=False)
