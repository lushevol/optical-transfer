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


def test_encrypt_chunk_reuses_session_key_for_same_password_and_salt(monkeypatch) -> None:
    import optical_transfer.sender.crypto as crypto

    calls = 0
    original_scrypt = crypto.hashlib.scrypt
    crypto._derive_key.cache_clear()

    def counting_scrypt(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_scrypt(*args, **kwargs)

    monkeypatch.setattr(crypto.hashlib, "scrypt", counting_scrypt)

    chunk_a = Chunk(chunk_index=0, data=b"alpha")
    chunk_b = Chunk(chunk_index=1, data=b"bravo")

    encrypt_chunk(
        chunk=chunk_a,
        password="correct horse battery staple",
        session_id=b"0123456789abcdef",
        salt=b"fedcba9876543210",
    )
    encrypt_chunk(
        chunk=chunk_b,
        password="correct horse battery staple",
        session_id=b"0123456789abcdef",
        salt=b"fedcba9876543210",
    )
    decrypt_chunk(
        encrypted_chunk=encrypt_chunk(
            chunk=chunk_a,
            password="correct horse battery staple",
            session_id=b"0123456789abcdef",
            salt=b"fedcba9876543210",
        ),
        password="correct horse battery staple",
        session_id=b"0123456789abcdef",
        salt=b"fedcba9876543210",
    )

    assert calls == 1


def test_decrypt_chunk_rejects_tampered_nonce() -> None:
    chunk = Chunk(chunk_index=2, data=b"payload-bytes")
    encrypted = encrypt_chunk(
        chunk=chunk,
        password="correct horse battery staple",
        session_id=b"0123456789abcdef",
        salt=b"fedcba9876543210",
    )

    tampered_nonce = bytes([encrypted.nonce[0] ^ 0x01]) + encrypted.nonce[1:]
    tampered = encrypted.with_nonce(tampered_nonce)

    with pytest.raises(InvalidTag):
        decrypt_chunk(
            encrypted_chunk=tampered,
            password="correct horse battery staple",
            session_id=b"0123456789abcdef",
            salt=b"fedcba9876543210",
        )
