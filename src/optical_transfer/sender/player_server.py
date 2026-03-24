from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from optical_transfer.config import DEFAULT_PLAYER_HOST, DEFAULT_PLAYER_PORT, DEFAULT_PLAYER_ROOT
from optical_transfer.sender.session import SessionPayloadSet


FALLBACK_PLAYER_ASSETS = {
    "index.html": """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Optical Transfer Player</title>
    <link rel=\"stylesheet\" href=\"/player.css\" />
  </head>
  <body>
    <main class=\"player-shell\">
      <section class=\"player-card\">
        <p class=\"eyebrow\">Optical Transfer</p>
        <h1>Sender preview</h1>
        <p id=\"status\">Loading packet feed...</p>
        <pre id=\"payload\" aria-label=\"packet payload feed\"></pre>
      </section>
    </main>
    <script src=\"/player.js\" defer></script>
  </body>
</html>
""",
    "player.js": """function renderFrame(packetSequence, index) {
  const status = document.getElementById(\"status\");
  const payload = document.getElementById(\"payload\");
  const packet = packetSequence[index];

  status.textContent = `Frame ${index + 1} of ${packetSequence.length}`;
  payload.textContent = packet;
}

function startPlayback(data) {
  const packetSequence = data.packet_sequence || [];
  if (packetSequence.length === 0) {
    document.getElementById(\"status\").textContent = \"No packets available.\";
    document.getElementById(\"payload\").textContent = \"\";
    return;
  }

  let index = 0;
  renderFrame(packetSequence, index);

  window.setInterval(() => {
    index = (index + 1) % packetSequence.length;
    renderFrame(packetSequence, index);
  }, 600);
}

async function loadPayload() {
  const status = document.getElementById(\"status\");
  const payload = document.getElementById(\"payload\");

  try {
    const response = await fetch(\"/payload.json\", { cache: \"no-store\" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    status.textContent = `Session ${data.session_id} ready.`;
    payload.textContent = \"Loading frame 1...\";
    startPlayback(data);
  } catch (error) {
    status.textContent = `Unable to load packet feed: ${error.message}`;
    payload.textContent = \"\";
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
  padding: 2rem;
}

.player-card {
  width: min(48rem, 100%);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 24px;
  padding: 2rem;
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

#payload {
  margin: 0;
  padding: 1rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.06);
  overflow: auto;
  min-height: 12rem;
}
""",
}


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

    def _read_asset(self, path: Path) -> bytes | None:
        if path.is_file():
            return path.read_bytes()

        fallback = FALLBACK_PLAYER_ASSETS.get(path.name)
        if fallback is None:
            return None
        return fallback.encode("utf-8")


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
    port: int = DEFAULT_PLAYER_PORT,
    player_root: Path | None = None,
) -> _PlayerHTTPServer:
    server = _PlayerHTTPServer((host, port), _PlayerRequestHandler)
    server.payloads = payloads
    server.player_root = Path(player_root or DEFAULT_PLAYER_ROOT)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
