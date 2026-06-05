from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from typing import List

from atlasx.foo.packets import PACKET_TYPE_DATA, PACKET_TYPE_MANIFEST
from atlasx.protocol.header import PacketHeader


_PROGRESS_DIR_NAME = ".atlasx-progress"


class ProgressStore:
    def __init__(self, output_root: Path) -> None:
        self.root = Path(output_root) / _PROGRESS_DIR_NAME

    def session_path(self, session_id: bytes) -> Path:
        return self.root / session_id.hex()

    def record_packet(self, header: PacketHeader, packet: bytes) -> Path:
        session_dir = self.session_path(header.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        _clean_stale_tmp_files(session_dir)

        packet_path = session_dir / _packet_filename(header)
        if packet_path.exists():
            return packet_path

        temporary_path = packet_path.with_suffix(packet_path.suffix + ".tmp")
        temporary_path.write_bytes(packet)
        temporary_path.replace(packet_path)
        return packet_path

    def load_packets(self, session_id: bytes) -> List[bytes]:
        session_dir = self.session_path(session_id)
        if not session_dir.is_dir():
            return []

        return [
            packet_path.read_bytes()
            for packet_path in sorted(session_dir.glob("*.pkt"), key=_packet_sort_key)
        ]

    def clear_session(self, session_id: bytes) -> None:
        rmtree(self.session_path(session_id), ignore_errors=True)


def _packet_filename(header: PacketHeader) -> str:
    if header.packet_type == PACKET_TYPE_MANIFEST:
        return "manifest.pkt"
    if header.packet_type == PACKET_TYPE_DATA:
        return f"chunk-{header.chunk_index:010d}.pkt"
    return f"packet-{header.packet_type:03d}-{header.chunk_index:010d}.pkt"


def _packet_sort_key(path: Path) -> tuple[int, str]:
    if path.name == "manifest.pkt":
        return (0, path.name)
    return (1, path.name)


def _clean_stale_tmp_files(directory: Path) -> None:
    for tmp_path in directory.glob("*.tmp"):
        tmp_path.unlink(missing_ok=True)
