from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    archive_path: Path
    archive_byte_length: int
    archive_hash: str
    original_directory_name: str | None = None


def archive_directory(source_dir: Path, output_path: Path) -> ArchiveResult:
    source_dir = Path(source_dir)
    output_path = Path(output_path)
    if not source_dir.is_dir():
        raise NotADirectoryError(source_dir)

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        archive_members = sorted(
            (
                p
                for p in source_dir.rglob("*")
                if p.is_file() or (p.is_dir() and not any(p.iterdir()))
            ),
            key=lambda path: (len(path.relative_to(source_dir).parts), path.relative_to(source_dir).as_posix()),
        )
        for file_path in archive_members:
            relative_path = file_path.relative_to(source_dir)
            tar_info = tarfile.TarInfo(name=relative_path.as_posix())
            tar_info.mode = 0o644
            tar_info.mtime = 0
            tar_info.uid = 0
            tar_info.gid = 0
            tar_info.uname = ""
            tar_info.gname = ""
            if file_path.is_dir():
                tar_info.type = tarfile.DIRTYPE
                tar_info.size = 0
                tar_info.mode = 0o755
                tar.addfile(tar_info)
            else:
                data = file_path.read_bytes()
                tar_info.size = len(data)
                tar.addfile(tar_info, io.BytesIO(data))

    archive_bytes = gzip.compress(tar_buffer.getvalue(), mtime=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(archive_bytes)

    return ArchiveResult(
        archive_path=output_path,
        archive_byte_length=len(archive_bytes),
        archive_hash=hashlib.sha256(archive_bytes).hexdigest(),
        original_directory_name=source_dir.name,
    )
