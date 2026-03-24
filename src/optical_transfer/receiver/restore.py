from __future__ import annotations

import io
import tarfile
import tempfile
from pathlib import Path


def restore_archive_bytes(archive_bytes: bytes, output_root: Path) -> Path:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    restored_dir = Path(tempfile.mkdtemp(prefix="restored-", dir=output_root))

    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        _extract_tar_members(archive, restored_dir)

    return restored_dir


def _extract_tar_members(archive: tarfile.TarFile, destination: Path) -> None:
    for member in archive.getmembers():
        target_path = (destination / member.name).resolve()
        if destination not in target_path.parents and target_path != destination:
            raise ValueError(f"refusing to extract path outside destination: {member.name}")

        if member.isdir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        if member.issym() or member.islnk():
            raise ValueError(f"refusing to extract link member: {member.name}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise ValueError(f"missing archive payload for member: {member.name}")
        with source, target_path.open("wb") as output:
            output.write(source.read())
