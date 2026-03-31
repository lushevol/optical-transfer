from __future__ import annotations

import base64
import io
from dataclasses import replace
from pathlib import Path

import pytest
import numpy as np
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image
from atlasx.protocol.constants import PROTOCOL_HEADER_SIZE
from atlasx.protocol.header import decode_header
import atlasx.cli as cli_module
from atlasx.inbound.preprocess import preprocess_frame
from atlasx.inbound import qr_decode as qr_decode_module
from atlasx.inbound.qr_decode import decode_qr_payload
from atlasx.outbound.packets import PACKET_TYPE_DATA, PACKET_TYPE_MANIFEST
from atlasx.outbound.player_server import build_player_payload
from atlasx.outbound.qr_payloads import decode_payload_image, encode_payload_image
from atlasx.outbound.session import build_session_payloads


def test_player_payload_exposes_fixed_size_frame_sequence(tmp_path: Path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "root.txt").write_text("root file\n", encoding="utf-8")
    (source_dir / "blob.bin").write_bytes(b"x" * 32768)

    session = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)
    payload = build_player_payload(session)

    frame_sequence = payload["frame_sequence"]

    assert len(frame_sequence) == len(session.packet_sequence)

    frame_sizes = set()
    for frame_data_url in frame_sequence:
        prefix, encoded = frame_data_url.split(",", 1)
        assert prefix.startswith("data:image/png;base64")
        image = Image.open(io.BytesIO(base64.b64decode(encoded)))
        frame_sizes.add(image.size)

    assert len(frame_sizes) == 1
    frame_size = next(iter(frame_sizes))
    assert frame_size[0] % 2 == 0
    assert frame_size[1] % 2 == 0


def test_inbound_command_restores_archive_from_synthetic_frames(tmp_path: Path, monkeypatch, capsys) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "root.txt").write_text("root file\n", encoding="utf-8")
    nested_dir = source_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "child.txt").write_text("nested file\n", encoding="utf-8")

    session = build_session_payloads(source_dir, password="correct horse battery staple", chunk_size=64)
    rendered_frames = [encode_payload_image(payload) for payload in session.packet_sequence]
    video_one = tmp_path / "recording1.mp4"
    video_two = tmp_path / "recording2.mp4"
    split_index = max(1, len(rendered_frames) // 2)
    video_frames = {
        video_one: rendered_frames[:split_index],
        video_two: rendered_frames[split_index:] or rendered_frames[-1:],
    }

    def fake_iter_video_frames(video_path):
        yield from video_frames[Path(video_path)]

    monkeypatch.setattr(cli_module, "iter_video_frames", fake_iter_video_frames, raising=False)

    parser = cli_module.build_parser()
    args = parser.parse_args(
        [
            "bar",
            str(video_one),
            str(video_two),
            "--password",
            "correct horse battery staple",
            "--output-root",
            str(tmp_path / "restored"),
        ]
    )

    result = cli_module.handle_inbound(args)
    captured = capsys.readouterr()

    restored_root = tmp_path / "restored"
    restored_dirs = list(restored_root.iterdir())

    assert result == 0
    assert "inbound: starting decode for 2 video(s)" in captured.out
    assert "inbound: reading video 1/2:" in captured.out
    assert "inbound: reassembling archive from" in captured.out
    assert "inbound: complete, restored directory:" in captured.out
    assert "input video count: 2" in captured.out
    assert "final archive hash result: match" in captured.out
    assert len(restored_dirs) == 1
    assert (restored_dirs[0] / "root.txt").read_text(encoding="utf-8") == "root file\n"
    assert (restored_dirs[0] / "nested" / "child.txt").read_text(encoding="utf-8") == "nested file\n"


def test_decode_payload_image_rejects_truncated_payload() -> None:
    from PIL import Image

    image = Image.new("1", (4, 4), 0)

    with pytest.raises(ValueError):
        decode_payload_image(image)


def test_preprocess_and_decode_frame_roundtrip(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.png"
    encode_payload_image(b"adapter payload").convert("RGB").save(frame_path)

    processed = preprocess_frame(frame_path)

    assert isinstance(processed, np.ndarray)
    assert processed.ndim == 2
    assert decode_qr_payload(processed) == b"adapter payload"


def test_real_qr_payload_survives_resize_and_decode() -> None:
    payload = b"camera-safe payload"
    image = encode_payload_image(payload)

    resized = image.convert("RGB").resize((image.width * 3, image.height * 3))
    processed = np.array(resized.convert("L"))

    assert decode_qr_payload(processed) == payload


def test_decode_qr_payload_returns_none_for_blank_frame() -> None:
    blank_frame = np.zeros((4, 4), dtype=np.uint8)

    assert decode_qr_payload(blank_frame) is None


def test_decode_qr_payload_returns_none_when_opencv_throws_on_invalid_points(monkeypatch) -> None:
    class FakeDetector:
        def detectAndDecode(self, _image):
            raise qr_decode_module.cv2.error(
                "OpenCV(4.10.0) qrcode.cpp:2951: error: (-2:Unspecified error) "
                "Invalid QR code source points"
            )

    monkeypatch.setattr(qr_decode_module.cv2, "QRCodeDetector", lambda: FakeDetector())

    blank_frame = np.zeros((32, 32), dtype=np.uint8)

    assert decode_qr_payload(blank_frame) is None


def test_qr_decode_module_exposes_only_planned_adapter_surface() -> None:
    assert hasattr(qr_decode_module, "decode_qr_payload")
    assert not hasattr(qr_decode_module, "decode_qr_frame")


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
