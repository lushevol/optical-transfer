from __future__ import annotations

import hashlib
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence

from atlasx.foo.chunker import Chunk


BUNDLE_FORMAT = "atlasx-bundle-v1"
_MAGIC = b"ATXB1"
_KIND_FILE = 1
_KIND_DIRECTORY = 2
_HEADER = struct.Struct(">5sB H Q Q I 32s")
_EXCLUDED_DIRECTORY_NAMES = {".atlasx-foo"}


@dataclass(frozen=True)
class BundleRecord:
    path: str
    offset: int
    file_size: int
    file_hash: bytes
    data: bytes
    is_directory: bool = False


@dataclass(frozen=True)
class BundleRestoreResult:
    restored_directory: Path
    restored_file_count: int
    partial_fragment_count: int


def build_bundle_chunks(source_dir: Path, chunk_size: int) -> list[Chunk]:
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise NotADirectoryError(source_dir)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    records: list[bytes] = []
    paths = sorted(
        (
            path
            for path in source_dir.rglob("*")
            if not _is_excluded(path, source_dir)
        ),
        key=lambda path: path.relative_to(source_dir).as_posix(),
    )
    for path in paths:
        relative_path = path.relative_to(source_dir).as_posix()
        if path.is_dir():
            if not any(path.iterdir()):
                records.append(_encode_directory(relative_path))
            continue
        if not path.is_file():
            continue

        file_data = path.read_bytes()
        file_hash = hashlib.sha256(file_data).digest()
        if not file_data:
            records.append(_encode_file(relative_path, 0, 0, file_hash, b""))
            continue
        for offset in range(0, len(file_data), chunk_size):
            records.append(
                _encode_file(
                    relative_path,
                    offset,
                    len(file_data),
                    file_hash,
                    file_data[offset : offset + chunk_size],
                )
            )

    if not records:
        records.append(_encode_directory("."))
    return [Chunk(chunk_index=index, data=data) for index, data in enumerate(records)]


def is_bundle_chunk(data: bytes) -> bool:
    return data.startswith(_MAGIC)


def decode_bundle_chunk(data: bytes) -> BundleRecord:
    if len(data) < _HEADER.size:
        raise ValueError("bundle chunk is truncated")
    magic, kind, path_length, offset, file_size, payload_length, file_hash = _HEADER.unpack(
        data[: _HEADER.size]
    )
    if magic != _MAGIC:
        raise ValueError("unsupported bundle chunk")
    expected_length = _HEADER.size + path_length + payload_length
    if len(data) != expected_length:
        raise ValueError("bundle chunk length does not match its header")

    path_bytes = data[_HEADER.size : _HEADER.size + path_length]
    try:
        path = path_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("bundle path is not valid UTF-8") from exc
    _validate_relative_path(path)
    payload = data[_HEADER.size + path_length :]

    if kind == _KIND_DIRECTORY:
        if offset != 0 or file_size != 0 or payload:
            raise ValueError("directory bundle chunk contains file data")
        return BundleRecord(path, 0, 0, file_hash, b"", is_directory=True)
    if kind != _KIND_FILE:
        raise ValueError("bundle chunk has an unknown record type")
    if path == ".":
        raise ValueError("bundle root marker cannot contain file data")
    if offset + len(payload) > file_size:
        raise ValueError("bundle file segment exceeds the declared file size")
    return BundleRecord(path, offset, file_size, file_hash, payload)


def bundle_stream_bytes(chunks: Iterable[bytes]) -> bytes:
    return b"".join(len(chunk).to_bytes(4, "big") + chunk for chunk in chunks)


def restore_bundle_chunks(chunks: Sequence[bytes], output_root: Path) -> BundleRestoreResult:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    restored_dir = Path(tempfile.mkdtemp(prefix="restored-", dir=output_root))

    directories: set[str] = set()
    files: dict[tuple[str, int, bytes], dict[int, bytes]] = {}
    file_identities: dict[str, tuple[int, bytes]] = {}
    for chunk in chunks:
        record = decode_bundle_chunk(chunk)
        if record.is_directory:
            if record.path in file_identities:
                raise ValueError(f"bundle path is both a file and directory: {record.path}")
            directories.add(record.path)
            continue
        if record.path in directories:
            raise ValueError(f"bundle path is both a file and directory: {record.path}")
        identity = (record.file_size, record.file_hash)
        existing_identity = file_identities.setdefault(record.path, identity)
        if existing_identity != identity:
            raise ValueError(f"conflicting bundle metadata for {record.path}")
        key = (record.path, record.file_size, record.file_hash)
        segments = files.setdefault(key, {})
        existing = segments.get(record.offset)
        if existing is not None and existing != record.data:
            raise ValueError(f"conflicting bundle segments for {record.path}")
        segments[record.offset] = record.data

    for directory in sorted(directories):
        if directory != ".":
            (restored_dir / directory).mkdir(parents=True, exist_ok=True)

    restored_file_count = 0
    partial_fragment_count = 0
    partial_root = restored_dir / ".atlasx-partial"
    for (relative_path, file_size, file_hash), segments in sorted(files.items()):
        ordered_segments = sorted(segments.items())
        cursor = 0
        complete = True
        assembled = bytearray()
        for offset, payload in ordered_segments:
            if offset != cursor:
                complete = False
                break
            assembled.extend(payload)
            cursor += len(payload)
        complete = complete and cursor == file_size
        complete = complete and hashlib.sha256(assembled).digest() == file_hash

        if complete:
            target = restored_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bytes(assembled))
            restored_file_count += 1
            continue

        for offset, payload in ordered_segments:
            fragment = partial_root / f"{relative_path}.part-{offset:016x}"
            fragment.parent.mkdir(parents=True, exist_ok=True)
            fragment.write_bytes(payload)
            partial_fragment_count += 1

    return BundleRestoreResult(
        restored_directory=restored_dir,
        restored_file_count=restored_file_count,
        partial_fragment_count=partial_fragment_count,
    )


def _encode_file(path: str, offset: int, file_size: int, file_hash: bytes, data: bytes) -> bytes:
    path_bytes = path.encode("utf-8")
    if len(path_bytes) > 0xFFFF:
        raise ValueError(f"bundle path is too long: {path}")
    return _HEADER.pack(
        _MAGIC,
        _KIND_FILE,
        len(path_bytes),
        offset,
        file_size,
        len(data),
        file_hash,
    ) + path_bytes + data


def _encode_directory(path: str) -> bytes:
    path_bytes = path.encode("utf-8")
    if len(path_bytes) > 0xFFFF:
        raise ValueError(f"bundle path is too long: {path}")
    return _HEADER.pack(
        _MAGIC,
        _KIND_DIRECTORY,
        len(path_bytes),
        0,
        0,
        0,
        b"\0" * 32,
    ) + path_bytes


def _validate_relative_path(path: str) -> None:
    parsed = PurePosixPath(path)
    if (
        not path
        or "\0" in path
        or "\\" in path
        or parsed.is_absolute()
        or ".." in parsed.parts
        or (path != "." and parsed.as_posix() != path)
    ):
        raise ValueError(f"unsafe bundle path: {path}")


def _is_excluded(path: Path, source_dir: Path) -> bool:
    return any(part in _EXCLUDED_DIRECTORY_NAMES for part in path.relative_to(source_dir).parts)
