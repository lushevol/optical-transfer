from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_CHUNK_SIZE = 64 * 1024
DEFAULT_PLAYER_HOST = "127.0.0.1"
DEFAULT_PLAYER_PORT = 8765
DEFAULT_PLAYER_ROOT = Path(__file__).resolve().parents[2] / "web" / "player"


@dataclass(frozen=True, slots=True)
class SenderConfig:
    source_dir: Path
    password: str
    chunk_size: int = DEFAULT_CHUNK_SIZE
    player_host: str = DEFAULT_PLAYER_HOST
    player_port: int = DEFAULT_PLAYER_PORT
    player_root: Path = DEFAULT_PLAYER_ROOT
