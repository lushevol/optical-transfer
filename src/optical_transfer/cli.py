from __future__ import annotations

import argparse
import hashlib
import tempfile
import webbrowser
from contextlib import suppress
import ipaddress
from pathlib import Path
from time import perf_counter
from threading import Event

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from optical_transfer.config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PLAYER_HOST,
    DEFAULT_PLAYER_PORT,
    SenderConfig,
)
from optical_transfer.receiver.collector import PacketCollector, VerifiedChunk
from optical_transfer.receiver.ffmpeg_frames import extract_frames
from optical_transfer.receiver.preprocess import preprocess_frame
from optical_transfer.receiver.qr_decode import decode_qr_payload
from optical_transfer.receiver.reassemble import reassemble_archive
from optical_transfer.receiver.report import SessionStats, build_session_report
from optical_transfer.receiver.restore import restore_archive_bytes
from optical_transfer.sender.crypto import ChunkCryptoSession
from optical_transfer.sender.manifest import manifest_from_json_bytes
from optical_transfer.sender.packets import PACKET_TYPE_DATA, PACKET_TYPE_MANIFEST, split_data_packet
from optical_transfer.sender.player_server import create_player_app
from optical_transfer.sender.session import build_session_payloads


def build_sender_config(args: argparse.Namespace) -> SenderConfig:
    player_host = _validate_player_host(args.player_host)
    return SenderConfig(
        source_dir=Path(args.source),
        password=args.password,
        chunk_size=args.chunk_size,
        player_host=player_host,
        player_port=args.player_port,
    )


def launch_player(url: str) -> bool:
    return webbrowser.open(url)


def build_preview_url(host: str, port: int) -> str:
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    else:
        with suppress(ValueError):
            if ipaddress.ip_address(host).version == 6:
                host = f"[{host}]"
    return f"http://{host}:{port}/"


def _validate_player_host(host: str) -> str:
    normalized = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        parsed_host = ipaddress.ip_address(normalized)
    except ValueError:
        return host
    if parsed_host.version == 6:
        raise ValueError("IPv6 player hosts are not supported by the sender preview server")
    return host


def wait_forever() -> None:
    with suppress(KeyboardInterrupt):
        Event().wait()


def run_preview_session(
    server,
    *,
    open_browser: bool = False,
    launch_fn=launch_player,
    wait_fn=wait_forever,
) -> None:
    preview_url = build_preview_url(server.server_address[0], server.server_address[1])
    try:
        launched = False
        if open_browser:
            try:
                launched = launch_fn(preview_url)
            except Exception:
                launched = False
        if not open_browser or not launched:
            print(f"Preview URL: {preview_url}")
        wait_fn()
    finally:
        server.shutdown()
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="optical-transfer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("--source", default=".")
    send_parser.add_argument("--password", default="")
    send_parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    send_parser.add_argument("--player-host", default=DEFAULT_PLAYER_HOST)
    send_parser.add_argument("--player-port", type=int, default=DEFAULT_PLAYER_PORT)
    send_parser.add_argument("--open-browser", action="store_true")

    receive_parser = subparsers.add_parser("receive")
    receive_parser.add_argument("videos", nargs="+")
    receive_parser.add_argument("--password", default="")
    receive_parser.add_argument("--output-root", default="restored")
    return parser


def handle_send(args: argparse.Namespace) -> int:
    config = build_sender_config(args)
    payloads = build_session_payloads(config.source_dir, config.password, config.chunk_size)
    server = create_player_app(
        payloads,
        host=config.player_host,
        port=config.player_port,
        player_root=config.player_root,
    )
    run_preview_session(
        server,
        open_browser=args.open_browser,
        launch_fn=launch_player,
        wait_fn=wait_forever,
    )
    return 0


def handle_receive(args: argparse.Namespace) -> int:
    video_paths = [Path(video) for video in args.videos]
    output_root = Path(args.output_root)

    collector = PacketCollector()
    crypto_sessions: dict[bytes, ChunkCryptoSession] = {}
    stats = {
        "input_video_count": len(video_paths),
        "total_extracted_frame_count": 0,
        "successfully_decoded_frame_count": 0,
        "raw_packet_count": 0,
        "deduplicated_valid_chunk_count": 0,
        "missing_chunk_count": 0,
        "authentication_failure_count": 0,
    }
    stage_timings: dict[str, float] = {
        "extract_frames": 0.0,
        "preprocess_decode": 0.0,
        "reassemble": 0.0,
        "restore": 0.0,
    }

    manifest = None
    session_id: bytes | None = None
    expected_total_chunks: int | None = None
    observed_kdf_salt: bytes | None = None

    for video_path in video_paths:
        extract_started = perf_counter()
        with tempfile.TemporaryDirectory(prefix=f"{video_path.stem}-frames-") as frame_dir:
            frame_paths = extract_frames(video_path, output_dir=Path(frame_dir))
            stage_timings["extract_frames"] += perf_counter() - extract_started
            stats["total_extracted_frame_count"] += len(frame_paths)

            decode_started = perf_counter()
            for frame_path in frame_paths:
                frame = preprocess_frame(frame_path)
                packet_bytes = decode_qr_payload(frame)
                if packet_bytes is None:
                    continue

                stats["successfully_decoded_frame_count"] += 1

                try:
                    header, encrypted_blob = split_data_packet(packet_bytes)
                except ValueError:
                    continue

                stats["raw_packet_count"] += 1

                if session_id is None:
                    session_id = header.session_id
                elif header.session_id != session_id:
                    raise ValueError("receive inputs contain multiple sessions")

                if observed_kdf_salt is None:
                    observed_kdf_salt = header.kdf_salt
                elif header.kdf_salt != observed_kdf_salt:
                    raise ValueError("receive inputs mix incompatible KDF salts")

                if expected_total_chunks is None:
                    expected_total_chunks = header.total_chunks
                elif header.total_chunks != expected_total_chunks:
                    raise ValueError("receive inputs mix incompatible chunk totals")

                if header.packet_type == PACKET_TYPE_MANIFEST:
                    manifest_plaintext = _decrypt_packet_payload(
                        encrypted_blob=encrypted_blob,
                        password=args.password,
                        header=header,
                        crypto_sessions=crypto_sessions,
                    )
                    decoded_manifest = manifest_from_json_bytes(manifest_plaintext)
                    if manifest is None:
                        manifest = decoded_manifest
                    elif manifest != decoded_manifest:
                        raise ValueError("receive inputs contain conflicting manifest packets")
                    if decoded_manifest.total_chunks != expected_total_chunks:
                        raise ValueError("manifest does not match packet chunk count")
                    continue

                if header.packet_type != PACKET_TYPE_DATA:
                    continue

                try:
                    chunk_payload = _decrypt_packet_payload(
                        encrypted_blob=encrypted_blob,
                        password=args.password,
                        header=header,
                        crypto_sessions=crypto_sessions,
                    )
                except InvalidTag:
                    stats["authentication_failure_count"] += 1
                    continue

                chunk = VerifiedChunk(
                    session_id=header.session_id,
                    chunk_index=header.chunk_index,
                    total_chunks=header.total_chunks,
                    data=chunk_payload,
                )
                if collector.add_chunk(chunk):
                    stats["deduplicated_valid_chunk_count"] += 1
            stage_timings["preprocess_decode"] += perf_counter() - decode_started

    if session_id is None or manifest is None or expected_total_chunks is None:
        raise ValueError("receive inputs did not include a complete manifest")

    chunks = collector.chunks(session_id)
    stats["missing_chunk_count"] = max(expected_total_chunks - len(chunks), 0)
    if stats["missing_chunk_count"]:
        raise ValueError("receive inputs are missing required chunks")

    reassemble_started = perf_counter()
    archive_bytes = reassemble_archive(chunks, expected_total_chunks)
    stage_timings["reassemble"] += perf_counter() - reassemble_started

    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    if archive_hash != manifest.archive_hash:
        raise ValueError("restored archive hash does not match manifest")

    restore_started = perf_counter()
    restored_dir = restore_archive_bytes(archive_bytes, output_root)
    stage_timings["restore"] += perf_counter() - restore_started

    session_stats = SessionStats(
        input_video_count=stats["input_video_count"],
        total_extracted_frame_count=stats["total_extracted_frame_count"],
        successfully_decoded_frame_count=stats["successfully_decoded_frame_count"],
        raw_packet_count=stats["raw_packet_count"],
        deduplicated_valid_chunk_count=stats["deduplicated_valid_chunk_count"],
        missing_chunk_count=stats["missing_chunk_count"],
        authentication_failure_count=stats["authentication_failure_count"],
        final_archive_hash_result="match",
        stage_timings=stage_timings,
        restored_directory=restored_dir,
    )
    print(build_session_report(session_stats))
    return 0


def _decrypt_packet_payload(
    *,
    encrypted_blob: bytes,
    password: str,
    header,
    crypto_sessions: dict[bytes, ChunkCryptoSession],
) -> bytes:
    if len(encrypted_blob) < 12 + 16:
        raise ValueError("encrypted payload is too short")

    crypto_session = crypto_sessions.get(header.kdf_salt)
    if crypto_session is None:
        crypto_session = ChunkCryptoSession(password=password, salt=header.kdf_salt)
        crypto_sessions[header.kdf_salt] = crypto_session

    nonce = encrypted_blob[:12]
    ciphertext = encrypted_blob[12:]
    aead = AESGCM(crypto_session.key())
    return aead.decrypt(
        nonce,
        ciphertext,
        _associated_data(
            session_id=header.session_id,
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "send":
        return handle_send(args)
    if args.command == "receive":
        return handle_receive(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
