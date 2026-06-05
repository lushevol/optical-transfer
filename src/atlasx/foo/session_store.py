from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from atlasx.foo.archive import ArchiveResult
from atlasx.foo.crypto import ChunkCryptoSession
from atlasx.foo.session import SessionPayloadSet
from atlasx.protocol.manifest_types import Manifest


_STORE_DIR_NAME = ".atlasx-foo"
_BUNDLE_FILE_NAME = "session.json"


def session_bundle_path(source_dir: Path) -> Path:
    return Path(source_dir) / _STORE_DIR_NAME / _BUNDLE_FILE_NAME


def save_session_bundle(source_dir: Path, payloads: SessionPayloadSet) -> Path:
    path = session_bundle_path(source_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Clean up any stale .tmp files left from a previous crash
    _clean_stale_tmp_files(path.parent)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    body = json.dumps(_bundle_payload(payloads), sort_keys=True, separators=(",", ":")).encode("utf-8")
    temporary_path.write_bytes(body)
    temporary_path.replace(path)
    return path


def load_session_bundle(source_dir: Path) -> SessionPayloadSet:
    path = session_bundle_path(source_dir)
    if not path.is_file():
        raise ValueError(
            "foo missing-chunk playback requires a saved session bundle; "
            "run a full foo run first"
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    return _session_from_bundle(payload, bundle_path=path)


def _bundle_payload(payloads: SessionPayloadSet) -> dict[str, Any]:
    return {
        "version": 1,
        "session_id": payloads.session_id.hex(),
        "kdf_salt": payloads.kdf_salt.hex(),
        "chunk_size": payloads.chunk_size,
        "total_chunks": payloads.total_chunks,
        "archive_result": {
            "archive_byte_length": payloads.archive_result.archive_byte_length,
            "archive_hash": payloads.archive_result.archive_hash,
            "original_directory_name": payloads.archive_result.original_directory_name,
        },
        "manifest": asdict(payloads.manifest),
        "manifest_packet": payloads.manifest_packet.hex(),
        "data_packets": [packet.hex() for packet in payloads.data_packets],
    }


def _session_from_bundle(payload: dict[str, Any], *, bundle_path: Path) -> SessionPayloadSet:
    if payload.get("version") != 1:
        raise ValueError("unsupported foo session bundle version")

    manifest = Manifest(**payload["manifest"])
    archive_payload = payload["archive_result"]
    archive_result = ArchiveResult(
        archive_path=bundle_path,
        archive_byte_length=int(archive_payload["archive_byte_length"]),
        archive_hash=str(archive_payload["archive_hash"]),
        original_directory_name=archive_payload.get("original_directory_name"),
    )
    kdf_salt = bytes.fromhex(payload["kdf_salt"])
    data_packets = [bytes.fromhex(packet) for packet in payload["data_packets"]]
    total_chunks = int(payload["total_chunks"])
    if len(data_packets) != total_chunks:
        raise ValueError("foo session bundle data packet count does not match total chunks")

    return SessionPayloadSet(
        session_id=bytes.fromhex(payload["session_id"]),
        archive_result=archive_result,
        archive_bytes=b"",
        manifest=manifest,
        crypto_session=ChunkCryptoSession(password="", salt=kdf_salt),
        kdf_salt=kdf_salt,
        chunk_size=int(payload["chunk_size"]),
        total_chunks=total_chunks,
        manifest_packet=bytes.fromhex(payload["manifest_packet"]),
        data_packets=data_packets,
    )


def _clean_stale_tmp_files(directory: Path) -> None:
    for tmp_path in directory.glob("*.tmp"):
        tmp_path.unlink(missing_ok=True)
