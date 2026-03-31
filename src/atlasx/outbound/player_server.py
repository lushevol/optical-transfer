from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

from atlasx.config import DEFAULT_PLAYER_HOST, DEFAULT_PLAYER_PORT, DEFAULT_PLAYER_ROOT
from atlasx.outbound.qr_payloads import encode_payload_data_url, required_canvas_size
from atlasx.outbound.session import SessionPayloadSet


FALLBACK_PLAYER_ASSETS = {
    "index.html": """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>AtlasX Player</title>
    <link rel=\"stylesheet\" href=\"/player.css\" />
  </head>
  <body>
    <main class=\"player-shell\">
      <section class=\"player-card\">
        <p class=\"eyebrow\">AtlasX</p>
        <h1>Outbound preview</h1>
        <p id=\"status\">Loading packet feed...</p>
        <div class=\"frame-shell\">
          <img id=\"frame\" alt=\"Current QR frame\" />
        </div>
      </section>
    </main>
    <script src=\"/player.js\" defer></script>
  </body>
</html>
""",
    "player.js": """function renderFrame(frameSequence, index) {
  const status = document.getElementById(\"status\");
  const frame = document.getElementById(\"frame\");
  const image = frameSequence[index];

  status.textContent = `Frame ${index + 1} of ${frameSequence.length}`;
  frame.src = image;
}

function startPlayback(data) {
  const frameSequence = data.frame_sequence || [];
  if (frameSequence.length === 0) {
    document.getElementById(\"status\").textContent = \"No packets available.\";
    document.getElementById(\"frame\").removeAttribute(\"src\");
    return;
  }

  let index = 0;
  renderFrame(frameSequence, index);

  window.setInterval(() => {
    index = (index + 1) % frameSequence.length;
    renderFrame(frameSequence, index);
  }, data.frame_interval_ms || 600);
}

async function loadPayload() {
  const status = document.getElementById(\"status\");
  const frame = document.getElementById(\"frame\");

  try {
    const response = await fetch(\"/payload.json\", { cache: \"no-store\" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    status.textContent = `Session ${data.session_id} ready.`;
    frame.removeAttribute(\"src\");
    startPlayback(data);
  } catch (error) {
    status.textContent = `Unable to load packet feed: ${error.message}`;
    frame.removeAttribute(\"src\");
  }
}

document.addEventListener(\"DOMContentLoaded\", loadPayload);
""",
    "player.css": """:root {
  color-scheme: dark;
  font-family: Inter, system-ui, sans-serif;
  background:
    radial-gradient(circle at top, rgba(255, 255, 255, 0.12), transparent 45%),
    linear-gradient(160deg, #0a1220 0%, #111c31 45%, #05070d 100%);
  color: #f4f7fb;
}

html,
body {
  margin: 0;
  min-height: 100%;
}

body {
  min-height: 100vh;
}

.player-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 1rem;
}

.player-card {
  width: min(96vw, 90rem);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 24px;
  padding: 1.25rem;
  background: rgba(6, 10, 18, 0.72);
  backdrop-filter: blur(18px);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
}

.eyebrow {
  margin: 0 0 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.78rem;
  color: #8ea4ff;
}

h1 {
  margin: 0;
  font-size: clamp(2.2rem, 4vw, 4rem);
  line-height: 0.95;
}

#status {
  margin: 1rem 0 1.5rem;
  color: rgba(244, 247, 251, 0.8);
}

.frame-shell {
  display: grid;
  place-items: center;
  padding: 1.5rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.06);
}

#frame {
  width: min(90vmin, 80rem);
  max-width: 100%;
  image-rendering: pixelated;
  background: white;
  border-radius: 12px;
}
""",
}


class _PlayerRequestHandler(BaseHTTPRequestHandler):
    server_version = "AtlasXPlayer/1.0"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlparse(self.path).path
        if path in {"", "/"}:
            self._serve_file(self.server.player_root / "index.html")
            return
        if path == "/payload.json":
            self._serve_json(
                build_player_payload(self.server.payloads, frame_interval_ms=self.server.frame_interval_ms)
            )
            return
        if path in {"/player.js", "/player.css"}:
            self._serve_file(self.server.player_root / path.lstrip("/"))
            return
        self.send_error(404, "Not Found")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - stdlib signature
        return

    def _serve_json(self, payload: Dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path) -> None:
        body = self._read_asset(path)
        if body is None:
            self.send_error(404, "Not Found")
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/"):
            content_type = f"{content_type}; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_asset(self, path: Path) -> Optional[bytes]:
        if path.is_file():
            return path.read_bytes()

        fallback = FALLBACK_PLAYER_ASSETS.get(path.name)
        if fallback is None:
            return None
        return fallback.encode("utf-8")


class _PlayerHTTPServer(ThreadingHTTPServer):
    payloads: SessionPayloadSet
    player_root: Path
    frame_interval_ms: int


def build_player_payload(payloads: SessionPayloadSet, *, frame_interval_ms: int = 600) -> Dict[str, object]:
    canvas_size = required_canvas_size(payloads.packet_sequence)
    return {
        "session_id": payloads.session_id.hex(),
        "chunk_size": payloads.chunk_size,
        "frame_interval_ms": frame_interval_ms,
        "total_chunks": payloads.total_chunks,
        "packet_sequence": [packet.hex() for packet in payloads.packet_sequence],
        "frame_size": canvas_size,
        "frame_sequence": [
            encode_payload_data_url(packet, canvas_size=canvas_size) for packet in payloads.packet_sequence
        ],
    }


def create_player_app(
    payloads: SessionPayloadSet,
    *,
    frame_interval_ms: int = 600,
    host: str = DEFAULT_PLAYER_HOST,
    port: int = DEFAULT_PLAYER_PORT,
    player_root: Optional[Path] = None,
) -> _PlayerHTTPServer:
    server = _PlayerHTTPServer((host, port), _PlayerRequestHandler)
    server.payloads = payloads
    server.player_root = Path(player_root or DEFAULT_PLAYER_ROOT)
    server.frame_interval_ms = frame_interval_ms

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
