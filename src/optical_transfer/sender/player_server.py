from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from optical_transfer.config import DEFAULT_PLAYER_HOST, DEFAULT_PLAYER_ROOT
from optical_transfer.sender.session import SessionPayloadSet


class _PlayerRequestHandler(BaseHTTPRequestHandler):
    server_version = "OpticalTransferPlayer/1.0"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlparse(self.path).path
        if path in {"", "/"}:
            self._serve_file(self.server.player_root / "index.html")
            return
        if path == "/payload.json":
            self._serve_json(build_player_payload(self.server.payloads))
            return
        if path in {"/player.js", "/player.css"}:
            self._serve_file(self.server.player_root / path.lstrip("/"))
            return
        self.send_error(404, "Not Found")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - stdlib signature
        return

    def _serve_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404, "Not Found")
            return

        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/"):
            content_type = f"{content_type}; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _PlayerHTTPServer(ThreadingHTTPServer):
    payloads: SessionPayloadSet
    player_root: Path


def build_player_payload(payloads: SessionPayloadSet) -> dict[str, object]:
    return {
        "session_id": payloads.session_id.hex(),
        "chunk_size": payloads.chunk_size,
        "total_chunks": payloads.total_chunks,
        "packet_sequence": [packet.hex() for packet in payloads.packet_sequence],
    }


def create_player_app(
    payloads: SessionPayloadSet,
    *,
    host: str = DEFAULT_PLAYER_HOST,
    port: int = 0,
    player_root: Path | None = None,
) -> _PlayerHTTPServer:
    server = _PlayerHTTPServer((host, port), _PlayerRequestHandler)
    server.payloads = payloads
    server.player_root = Path(player_root or DEFAULT_PLAYER_ROOT)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
