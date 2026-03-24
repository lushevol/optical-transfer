from __future__ import annotations

import io
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from optical_transfer.protocol.constants import PROTOCOL_HEADER_SIZE
from optical_transfer.protocol.header import decode_header
from optical_transfer.receiver.ffmpeg_frames import extract_frames
from optical_transfer.receiver.preprocess import preprocess_frame
from optical_transfer.receiver.qr_decode import decode_qr_frame
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
        plaintext = _decrypt_packet(
            encrypted_blob=encrypted_blob,
            session=session,
            header=header,
        )
        if header.packet_type == PACKET_TYPE_MANIFEST:
            manifest = manifest_from_json_bytes(plaintext)
            assert manifest.archive_hash == session.manifest.archive_hash
        elif header.packet_type == PACKET_TYPE_DATA:
            decrypted_chunks.append((header.chunk_index, plaintext))

    archive_bytes = b"".join(chunk_data for _, chunk_data in sorted(decrypted_chunks, key=lambda item: item[0]))
    assert archive_bytes == session.archive_bytes

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


def test_extract_frames_builds_ffmpeg_command_and_collects_frames(tmp_path: Path) -> None:
    video_path = tmp_path / "session.mp4"
    video_path.write_bytes(b"video")
    output_dir = tmp_path / "frames"

    seen_command: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> object:
        seen_command[:] = command
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "frame_000001.png").write_bytes(b"first")
        (output_dir / "frame_000002.png").write_bytes(b"second")
        return object()

    frame_paths = extract_frames(video_path, output_dir=output_dir, runner=fake_run)

    assert seen_command[:3] == ["ffmpeg", "-i", str(video_path)]
    assert "-vsync" in seen_command
    assert frame_paths == [output_dir / "frame_000001.png", output_dir / "frame_000002.png"]


def test_preprocess_and_decode_frame_roundtrip() -> None:
    image = encode_payload_image(b"adapter payload").convert("RGB")

    processed = preprocess_frame(image)

    assert processed.mode == "1"
    assert decode_qr_frame(image) == b"adapter payload"


def test_tampering_packet_type_in_header_breaks_authentication(tmp_path: Path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_text("hello world\n", encoding="utf-8")

    session = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)
    packet_bytes = session.packet_payloads[-1]
    header = decode_header(packet_bytes[:PROTOCOL_HEADER_SIZE])
    tampered_header = replace(
        header,
        packet_type=PACKET_TYPE_MANIFEST if header.packet_type == PACKET_TYPE_DATA else PACKET_TYPE_DATA,
        header_crc=None,
    )

    with pytest.raises(InvalidTag):
        _decrypt_packet(
            encrypted_blob=packet_bytes[PROTOCOL_HEADER_SIZE:],
            session=session,
            header=tampered_header,
        )


def test_tampering_payload_length_in_header_breaks_authentication(tmp_path: Path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_text("hello world\n", encoding="utf-8")

    session = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)
    packet_bytes = session.packet_payloads[-1]
    header = decode_header(packet_bytes[:PROTOCOL_HEADER_SIZE])
    tampered_header = replace(
        header,
        payload_length=header.payload_length - 1,
        header_crc=None,
    )

    with pytest.raises(InvalidTag):
        _decrypt_packet(
            encrypted_blob=packet_bytes[PROTOCOL_HEADER_SIZE:],
            session=session,
            header=tampered_header,
        )


def _decrypt_packet(*, encrypted_blob: bytes, session, header) -> bytes:
    aead = AESGCM(session.crypto_session.key())
    return aead.decrypt(
        encrypted_blob[:12],
        encrypted_blob[12:],
        _associated_data(
            session_id=session.session_id,
            packet_type=header.packet_type,
            chunk_index=header.chunk_index,
            total_chunks=header.total_chunks,
            payload_length=header.payload_length,
            kdf_salt=header.kdf_salt,
        ),
    )


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
