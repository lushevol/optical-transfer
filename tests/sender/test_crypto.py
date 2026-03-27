from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from cryptography.exceptions import InvalidTag

from optical_transfer.sender.chunker import Chunk
from optical_transfer.sender.crypto import (
    ChunkCryptoSession,
    decrypt_chunk,
    encrypt_chunk,
)


def test_encrypt_chunk_roundtrip_succeeds_with_matching_password() -> None:
    chunk = Chunk(chunk_index=4, data=b"payload-bytes")
    session = ChunkCryptoSession(
        password="correct horse battery staple",
        salt=b"fedcba9876543210",
    )

    encrypted = encrypt_chunk(
        chunk=chunk,
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )

    decrypted = decrypt_chunk(
        encrypted_chunk=encrypted,
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )

    assert decrypted == chunk


def test_encrypt_chunk_rejects_tampered_ciphertext() -> None:
    chunk = Chunk(chunk_index=1, data=b"payload-bytes")
    session = ChunkCryptoSession(
        password="correct horse battery staple",
        salt=b"fedcba9876543210",
    )
    encrypted = encrypt_chunk(
        chunk=chunk,
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )

    tampered = encrypted.with_ciphertext(bytes([encrypted.ciphertext[0] ^ 0x01]) + encrypted.ciphertext[1:])

    with pytest.raises(InvalidTag):
        decrypt_chunk(
            encrypted_chunk=tampered,
            crypto_session=session,
            session_id=b"0123456789abcdef",
        )


def test_encrypt_chunk_reuses_session_key_within_explicit_session(monkeypatch) -> None:
    import optical_transfer.sender.crypto as crypto

    calls = 0
    original_derive_key = crypto._derive_key

    def counting_derive_key(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_derive_key(*args, **kwargs)

    monkeypatch.setattr(crypto, "_derive_key", counting_derive_key)

    session = ChunkCryptoSession(
        password="correct horse battery staple",
        salt=b"fedcba9876543210",
    )
    chunk_a = Chunk(chunk_index=0, data=b"alpha")
    chunk_b = Chunk(chunk_index=1, data=b"bravo")

    encrypt_chunk(
        chunk=chunk_a,
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )
    encrypt_chunk(
        chunk=chunk_b,
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )
    decrypt_chunk(
        encrypted_chunk=encrypt_chunk(
            chunk=chunk_a,
            crypto_session=session,
            session_id=b"0123456789abcdef",
        ),
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )

    assert calls == 1


def test_chunk_crypto_session_clear_forces_rederivation(monkeypatch) -> None:
    import optical_transfer.sender.crypto as crypto

    calls = 0
    original_derive_key = crypto._derive_key

    def counting_derive_key(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_derive_key(*args, **kwargs)

    monkeypatch.setattr(crypto, "_derive_key", counting_derive_key)

    session = ChunkCryptoSession(
        password="correct horse battery staple",
        salt=b"fedcba9876543210",
    )
    chunk = Chunk(chunk_index=3, data=b"charlie")

    encrypt_chunk(
        chunk=chunk,
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )
    session.clear()
    encrypt_chunk(
        chunk=chunk,
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )

    assert calls == 2


def test_chunk_crypto_session_hash_stays_stable_across_key_cache_mutations() -> None:
    session = ChunkCryptoSession(
        password="correct horse battery staple",
        salt=b"fedcba9876543210",
    )
    registry = {session: "present"}
    initial_hash = hash(session)

    session.key()
    assert hash(session) == initial_hash
    assert registry[session] == "present"

    session.clear()
    assert hash(session) == initial_hash
    assert registry[session] == "present"


def test_chunk_crypto_session_rejects_mutating_inputs_after_key_derivation() -> None:
    session = ChunkCryptoSession(
        password="correct horse battery staple",
        salt=b"fedcba9876543210",
    )

    session.key()

    with pytest.raises(FrozenInstanceError):
        session.password = "different password"

    with pytest.raises(FrozenInstanceError):
        session.salt = b"0123456789abcdef"


def test_decrypt_chunk_rejects_tampered_nonce() -> None:
    chunk = Chunk(chunk_index=2, data=b"payload-bytes")
    session = ChunkCryptoSession(
        password="correct horse battery staple",
        salt=b"fedcba9876543210",
    )
    encrypted = encrypt_chunk(
        chunk=chunk,
        crypto_session=session,
        session_id=b"0123456789abcdef",
    )

    tampered_nonce = bytes([encrypted.nonce[0] ^ 0x01]) + encrypted.nonce[1:]
    tampered = encrypted.with_nonce(tampered_nonce)

    with pytest.raises(InvalidTag):
        decrypt_chunk(
            encrypted_chunk=tampered,
            crypto_session=session,
            session_id=b"0123456789abcdef",
        )


def test_encrypt_chunk_uses_distinct_nonces_for_repeated_chunk_index() -> None:
    session = ChunkCryptoSession(
        password="correct horse battery staple",
        salt=b"fedcba9876543210",
    )
    session_id = b"0123456789abcdef"
    chunk = Chunk(chunk_index=9, data=b"payload-bytes")

    encrypted_a = encrypt_chunk(chunk=chunk, crypto_session=session, session_id=session_id)
    encrypted_b = encrypt_chunk(chunk=chunk, crypto_session=session, session_id=session_id)

    assert encrypted_a.nonce != encrypted_b.nonce
    assert decrypt_chunk(encrypted_chunk=encrypted_a, crypto_session=session, session_id=session_id) == chunk
    assert decrypt_chunk(encrypted_chunk=encrypted_b, crypto_session=session, session_id=session_id) == chunk
