from __future__ import annotations

import argparse
import hashlib
import os
import sys
import webbrowser
from contextlib import suppress
import ipaddress
from pathlib import Path
from time import perf_counter
from threading import Event
from typing import Dict, List, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from atlasx.config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_FRAME_INTERVAL_MS,
    DEFAULT_PLAYER_HOST,
    DEFAULT_PLAYER_PORT,
    FooConfig,
)
from atlasx.foo.crypto import ChunkCryptoSession
from atlasx.foo.manifest import manifest_from_json_bytes
from atlasx.foo.packets import PACKET_TYPE_DATA, PACKET_TYPE_MANIFEST, split_data_packet
from atlasx.foo.player_server import create_player_app
from atlasx.foo.session import build_session_payloads, filter_session_payloads
from atlasx.foo.session_store import load_session_bundle, save_session_bundle
from atlasx.bar.restore import restore_archive_bytes as _default_restore_archive_bytes

iter_video_frames = None
iter_decoded_frames = None
preprocess_frame = None
decode_qr_payload = None
reassemble_archive = None
build_session_report = None
restore_archive_bytes = _default_restore_archive_bytes


def build_foo_config(args: argparse.Namespace) -> FooConfig:
    player_host = _validate_player_host(args.player_host)
    return FooConfig(
        source_dir=Path(args.source),
        password=args.password,
        chunk_size=args.chunk_size,
        frame_interval_ms=args.frame_interval_ms,
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
        raise ValueError("IPv6 player hosts are not supported by the foo preview server")
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
    parser = argparse.ArgumentParser(prog="atlasx")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_foo_arguments(subparsers.add_parser("foo"))
    _add_bar_arguments(subparsers.add_parser("bar"))

    return parser


def _add_foo_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", default=".")
    parser.add_argument("--password", default="")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--frame-interval-ms", type=int, default=DEFAULT_FRAME_INTERVAL_MS)
    parser.add_argument("--player-host", default=DEFAULT_PLAYER_HOST)
    parser.add_argument("--player-port", type=int, default=DEFAULT_PLAYER_PORT)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--missing-chunks")


def _add_bar_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("videos", nargs="+")
    parser.add_argument("--password", default="")
    parser.add_argument("--output-root", default="restored")
    parser.add_argument(
        "--decode-workers",
        type=_positive_int,
        default=default_decode_worker_count(),
    )


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def default_decode_worker_count() -> int:
    return max(2, min(os.cpu_count() or 2, 8))


def handle_foo(args: argparse.Namespace) -> int:
    config = build_foo_config(args)
    if args.missing_chunks is None:
        payloads = build_session_payloads(config.source_dir, config.password, config.chunk_size)
        save_session_bundle(config.source_dir, payloads)
    else:
        missing_indexes = parse_missing_chunk_indexes(args.missing_chunks)
        payloads = filter_session_payloads(
            load_session_bundle(config.source_dir),
            missing_indexes,
        )
    server = create_player_app(
        payloads,
        frame_interval_ms=config.frame_interval_ms,
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


def parse_missing_chunk_indexes(value: str) -> list[int]:
    raw_parts = value.split(",")
    indexes: list[int] = []
    for raw_part in raw_parts:
        part = raw_part.strip()
        if not part:
            raise ValueError("missing chunk indexes must not contain empty entries")
        try:
            index = int(part)
        except ValueError as exc:
            raise ValueError(f"invalid missing chunk index: {part}") from exc
        if index < 0:
            raise ValueError("missing chunk indexes must not be negative")
        indexes.append(index)

    if not indexes:
        raise ValueError("missing chunk indexes must not be empty")
    if len(set(indexes)) != len(indexes):
        raise ValueError("missing chunk indexes must not contain duplicates")
    return sorted(indexes)


def handle_bar(args: argparse.Namespace) -> int:
    from atlasx.bar.collector import PacketCollector, VerifiedChunk
    from atlasx.bar.progress import ProgressStore
    from atlasx.bar.report import SessionStats

    iter_video_frames_fn = iter_video_frames
    if iter_video_frames_fn is None:
        from atlasx.bar.ffmpeg_frames import iter_video_frames as iter_video_frames_fn

    iter_decoded_frames_fn = iter_decoded_frames
    if iter_decoded_frames_fn is None:
        from atlasx.bar.frame_decode import iter_decoded_frames as iter_decoded_frames_fn

    preprocess_frame_fn = preprocess_frame
    if preprocess_frame_fn is None:
        from atlasx.bar.preprocess import preprocess_frame as preprocess_frame_fn

    decode_qr_payload_fn = decode_qr_payload
    if decode_qr_payload_fn is None:
        from atlasx.bar.qr_decode import decode_qr_payload as decode_qr_payload_fn

    reassemble_archive_fn = reassemble_archive
    if reassemble_archive_fn is None:
        from atlasx.bar.reassemble import reassemble_archive as reassemble_archive_fn

    build_session_report_fn = build_session_report
    if build_session_report_fn is None:
        from atlasx.bar.report import build_session_report as build_session_report_fn

    restore_archive_bytes_fn = restore_archive_bytes
    if restore_archive_bytes_fn is None:
        from atlasx.bar.restore import restore_archive_bytes as restore_archive_bytes_fn

    video_paths = [Path(video) for video in args.videos]
    output_root = Path(args.output_root)
    _bar_log(f"bar: starting decode for {len(video_paths)} video(s)")
    _bar_log(f"bar: output root: {output_root}")
    if args.password:
        _bar_log("bar: password provided")
    else:
        _bar_log("bar: no password provided")

    collector = PacketCollector()
    progress_store = ProgressStore(output_root)
    crypto_sessions: Dict[bytes, ChunkCryptoSession] = {}
    stats = {
        "input_video_count": len(video_paths),
        "total_extracted_frame_count": 0,
        "successfully_decoded_frame_count": 0,
        "raw_packet_count": 0,
        "deduplicated_valid_chunk_count": 0,
        "missing_chunk_count": 0,
        "authentication_failure_count": 0,
    }
    stage_timings: Dict[str, float] = {
        "extract_frames": 0.0,
        "preprocess_decode": 0.0,
        "reassemble": 0.0,
        "restore": 0.0,
    }

    manifest = None
    session_id: Optional[bytes] = None
    expected_total_chunks: Optional[int] = None
    observed_kdf_salt: Optional[bytes] = None
    total_accepted_chunks = 0
    loaded_progress_sessions: set[bytes] = set()

    def load_saved_progress(progress_session_id: bytes) -> None:
        if progress_session_id in loaded_progress_sessions:
            return
        loaded_progress_sessions.add(progress_session_id)

        saved_packets = progress_store.load_packets(progress_session_id)
        if not saved_packets:
            return

        _bar_log(
            "bar: loaded "
            f"{len(saved_packets)} saved packet(s) from "
            f"{progress_store.session_path(progress_session_id)}"
        )
        for saved_packet in saved_packets:
            process_packet(saved_packet, record_progress=False)

    def process_packet(packet_bytes: bytes, *, record_progress: bool) -> bool:
        nonlocal manifest
        nonlocal observed_kdf_salt
        nonlocal session_id
        nonlocal expected_total_chunks
        nonlocal total_accepted_chunks

        try:
            header, encrypted_blob = split_data_packet(packet_bytes)
        except ValueError:
            return False

        stats["raw_packet_count"] += 1

        if session_id is None:
            session_id = header.session_id
            _bar_log(
                "bar: session identified "
                f"({session_id.hex()[:16]}...)"
            )
            load_saved_progress(session_id)
        elif header.session_id != session_id:
            raise ValueError("bar inputs contain multiple sessions")

        if observed_kdf_salt is None:
            observed_kdf_salt = header.kdf_salt
        elif header.kdf_salt != observed_kdf_salt:
            raise ValueError("bar inputs mix incompatible KDF salts")

        if expected_total_chunks is None:
            expected_total_chunks = header.total_chunks
        elif header.total_chunks != expected_total_chunks:
            raise ValueError("bar inputs mix incompatible chunk totals")

        if header.packet_type == PACKET_TYPE_MANIFEST:
            _bar_log(
                "bar: manifest packet decoded "
                f"({stats['raw_packet_count']} raw packet(s) seen)"
            )
            try:
                manifest_plaintext = _decrypt_packet_payload(
                    encrypted_blob=encrypted_blob,
                    password=args.password,
                    header=header,
                    crypto_sessions=crypto_sessions,
                )
                decoded_manifest = manifest_from_json_bytes(manifest_plaintext)
            except InvalidTag:
                stats["authentication_failure_count"] += 1
                return False
            except (TypeError, UnicodeDecodeError, ValueError):
                return False

            if manifest is None:
                manifest = decoded_manifest
            elif manifest != decoded_manifest:
                raise ValueError("bar inputs contain conflicting manifest packets")
            if decoded_manifest.total_chunks != expected_total_chunks:
                raise ValueError("manifest does not match packet chunk count")
            _bar_log(
                "bar: manifest validated "
                f"({decoded_manifest.total_chunks} total chunk(s))"
            )
            if record_progress:
                progress_store.record_packet(header, packet_bytes)
            return True

        if header.packet_type != PACKET_TYPE_DATA:
            return False

        try:
            chunk_payload = _decrypt_packet_payload(
                encrypted_blob=encrypted_blob,
                password=args.password,
                header=header,
                crypto_sessions=crypto_sessions,
            )
        except InvalidTag:
            stats["authentication_failure_count"] += 1
            return False
        except ValueError:
            return False

        chunk = VerifiedChunk(
            session_id=header.session_id,
            chunk_index=header.chunk_index,
            total_chunks=header.total_chunks,
            data=chunk_payload,
        )
        if collector.add_chunk(chunk):
            stats["deduplicated_valid_chunk_count"] += 1
            total_accepted_chunks += 1
            if record_progress:
                progress_store.record_packet(header, packet_bytes)
            if (
                total_accepted_chunks == 1
                or total_accepted_chunks % 25 == 0
                or total_accepted_chunks == expected_total_chunks
            ):
                _bar_log(
                    "bar: accepted "
                    f"{total_accepted_chunks}/{expected_total_chunks} chunk(s)"
                )
            return True

        return False

    for video_index, video_path in enumerate(video_paths, start=1):
        _bar_log(
            f"bar: reading video {video_index}/{len(video_paths)}: {video_path}"
        )
        extract_started = perf_counter()
        decode_started = perf_counter()
        video_frame_count = 0
        video_decoded_count = 0
        frame_results = iter_decoded_frames_fn(
            iter_video_frames_fn(video_path),
            preprocess_frame_fn,
            decode_qr_payload_fn,
            worker_count=args.decode_workers,
        )
        for frame_result in frame_results:
            stats["total_extracted_frame_count"] += 1
            video_frame_count = frame_result.frame_number

            packet_bytes = frame_result.packet_bytes
            if packet_bytes is None:
                if video_frame_count == 1 or video_frame_count % 25 == 0:
                    _bar_log(
                        "bar: "
                        f"{video_path.name}: extracted {video_frame_count} frame(s), "
                        f"decoded {video_decoded_count} QR payload(s)"
                    )
                continue

            stats["successfully_decoded_frame_count"] += 1
            video_decoded_count += 1

            process_packet(packet_bytes, record_progress=True)
            if video_frame_count == 1 or video_frame_count % 25 == 0:
                _bar_log(
                    "bar: "
                    f"{video_path.name}: extracted {video_frame_count} frame(s), "
                    f"decoded {video_decoded_count} QR payload(s)"
                )
        stage_timings["extract_frames"] += perf_counter() - extract_started
        stage_timings["preprocess_decode"] += perf_counter() - decode_started

    if session_id is None or manifest is None or expected_total_chunks is None:
        if session_id is None:
            raise ValueError("bar inputs did not include a complete manifest")
        raise ValueError(
            "bar inputs did not include a complete manifest; "
            f"progress saved in {progress_store.session_path(session_id)}"
        )

    chunks = collector.chunks(session_id)
    stats["missing_chunk_count"] = max(expected_total_chunks - len(chunks), 0)
    if stats["missing_chunk_count"]:
        found_indexes = {chunk.chunk_index for chunk in chunks}
        missing_indexes = sorted(set(range(expected_total_chunks)) - found_indexes)
        raise ValueError(
            "bar inputs are missing required chunks: "
            f"{missing_indexes}; progress saved in {progress_store.session_path(session_id)}"
        )

    _bar_log(
        "bar: reassembling archive "
        f"from {len(chunks)}/{expected_total_chunks} chunk(s)"
    )
    reassemble_started = perf_counter()
    archive_bytes = reassemble_archive_fn(chunks, expected_total_chunks)
    stage_timings["reassemble"] += perf_counter() - reassemble_started

    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    if archive_hash != manifest.archive_hash:
        raise ValueError("restored archive hash does not match manifest")

    _bar_log(f"bar: restoring archive into {output_root}")
    restore_started = perf_counter()
    restored_dir = restore_archive_bytes_fn(archive_bytes, output_root)
    stage_timings["restore"] += perf_counter() - restore_started
    progress_store.clear_session(session_id)

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
    print(build_session_report_fn(session_stats))
    _bar_log(f"bar: complete, restored directory: {restored_dir}")
    return 0


def _decrypt_packet_payload(
    *,
    encrypted_blob: bytes,
    password: str,
    header,
    crypto_sessions: Dict[bytes, ChunkCryptoSession],
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


def _bar_log(message: str) -> None:
    print(message, flush=True)


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        build_parser().parse_args(argv)  # pragma: no cover
        return 0

    command, command_args = argv[0], argv[1:]
    if command == "foo":
        args = _parse_command_args(_build_foo_command_parser(), command_args)
        return handle_foo(args)
    if command == "bar":
        args = _parse_command_args(_build_bar_command_parser(), command_args)
        return handle_bar(args)

    build_parser().parse_args(argv)  # pragma: no cover
    return 0


def _build_foo_command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlasx foo")
    _add_foo_arguments(parser)
    return parser


def _build_bar_command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlasx bar")
    _add_bar_arguments(parser)
    return parser


def _parse_command_args(parser: argparse.ArgumentParser, argv: List[str]) -> argparse.Namespace:
    parse_intermixed_args = getattr(parser, "parse_intermixed_args", None)
    if parse_intermixed_args is not None:
        try:
            return parse_intermixed_args(argv)
        except TypeError:
            pass
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
