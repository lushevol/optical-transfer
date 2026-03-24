from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag

from optical_transfer.sender.chunker import Chunk
from optical_transfer.sender.crypto import decrypt_chunk, encrypt_chunk


def test_encrypt_chunk_roundtrip_succeeds_with_matching_password() -> None:
    chunk = Chunk(chunk_index=4, data=b"payload-bytes")

    encrypted = encrypt_chunk(
        chunk=chunk,
        password="correct horse battery staple",
        session_id=b"0123456789abcdef",
        salt=b"fedcba9876543210",
    )

    decrypted = decrypt_chunk(
        encrypted_chunk=encrypted,
        password="correct horse battery staple",
        session_id=b"0123456789abcdef",
        salt=b"fedcba9876543210",
    )

    assert decrypted == chunk


def test_encrypt_chunk_rejects_tampered_ciphertext() -> None:
    chunk = Chunk(chunk_index=1, data=b"payload-bytes")
    encrypted = encrypt_chunk(
        chunk=chunk,
        password="correct horse battery staple",
        session_id=b"0123456789abcdef",
        salt=b"fedcba9876543210",
    )

    tampered = encrypted.with_ciphertext(bytes([encrypted.ciphertext[0] ^ 0x01]) + encrypted.ciphertext[1:])

    with pytest.raises(InvalidTag):
        decrypt_chunk(
            encrypted_chunk=tampered,
            password="correct horse battery staple",
            session_id=b"0123456789abcdef",
            salt=b"fedcba9876543210",
        )
