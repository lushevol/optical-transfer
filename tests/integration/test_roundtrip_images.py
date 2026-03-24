from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest
from optical_transfer.protocol.constants import PROTOCOL_HEADER_SIZE
from optical_transfer.protocol.header import decode_header
from optical_transfer.sender.crypto import EncryptedChunk, decrypt_chunk
from optical_transfer.sender.packets import PACKET_TYPE_DATA, PACKET_TYPE_MANIFEST
from optical_transfer.sender.qr_payloads import decode_payload_image, encode_payload_image
from optical_transfer.sender.session import build_session_payloads
from optical_transfer.sender.manifest import manifest_from_json_bytes


def test_image_based_roundtrip_restores_archive_without_video(tmp_path: Path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "root.txt").write_text("root file\n", encoding="utf-8")
    nested_dir = source_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "child.txt").write_text("nested file\n", encoding="utf-8")

    session = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)

    rendered_images = [encode_payload_image(payload) for payload in session.packet_payloads]
    decoded_packets = [decode_payload_image(image) for image in rendered_images]
    assert decoded_packets == session.packet_payloads

    decrypted_chunks = []
    for packet_bytes in decoded_packets:
        header = decode_header(packet_bytes[:PROTOCOL_HEADER_SIZE])
        encrypted_blob = packet_bytes[PROTOCOL_HEADER_SIZE:]
        encrypted_chunk = EncryptedChunk(
            chunk_index=header.chunk_index,
            nonce=encrypted_blob[:12],
            ciphertext=encrypted_blob[12:],
        )
        plaintext_chunk = decrypt_chunk(
            encrypted_chunk=encrypted_chunk,
            crypto_session=session.crypto_session,
            session_id=session.session_id,
        )
        if header.packet_type == PACKET_TYPE_MANIFEST:
            manifest = manifest_from_json_bytes(plaintext_chunk.data)
            assert manifest.archive_hash == session.manifest.archive_hash
        elif header.packet_type == PACKET_TYPE_DATA:
            decrypted_chunks.append(plaintext_chunk)

    archive_bytes = b"".join(chunk.data for chunk in sorted(decrypted_chunks, key=lambda chunk: chunk.chunk_index))
    assert archive_bytes == session.archive_result.archive_path.read_bytes()

    restored_dir = tmp_path / "restored"
    restored_dir.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
        tar.extractall(restored_dir)

    assert (restored_dir / "root.txt").read_text(encoding="utf-8") == "root file\n"
    assert (restored_dir / "nested" / "child.txt").read_text(encoding="utf-8") == "nested file\n"


def test_decode_payload_image_rejects_truncated_payload() -> None:
    from PIL import Image

    image = Image.new("1", (4, 4), 0)

    with pytest.raises(ValueError):
        decode_payload_image(image)
