# Optical Transfer V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI-based V1 optical transfer tool that packages one directory into authenticated QR packets, plays them in Chromium, and reconstructs the directory from one or more recorded videos on macOS.

**Architecture:** Use Python for the CLI, protocol, crypto, and receiver pipeline, with a small static web player for fullscreen QR playback. Keep the V1 pipeline simple: `tar.gz -> chunk -> AEAD -> packet -> QR`, with a matching offline receiver that extracts frames, preprocesses images, decodes QR payloads, deduplicates packets, verifies chunks, and restores the archive.

**Tech Stack:** Python 3.12, `pytest`, `ffmpeg`, `opencv-python`, `qrcode`, `cryptography`, `pyzbar` or ZXing-backed decoder, static HTML/CSS/JS for the player

---

## Planned File Structure

### Core package

- Create: `src/optical_transfer/__init__.py`
- Create: `src/optical_transfer/cli.py`
- Create: `src/optical_transfer/config.py`
- Create: `src/optical_transfer/logging.py`

### Sender

- Create: `src/optical_transfer/sender/archive.py`
- Create: `src/optical_transfer/sender/chunker.py`
- Create: `src/optical_transfer/sender/crypto.py`
- Create: `src/optical_transfer/sender/manifest.py`
- Create: `src/optical_transfer/sender/packets.py`
- Create: `src/optical_transfer/sender/session.py`
- Create: `src/optical_transfer/sender/qr_payloads.py`
- Create: `src/optical_transfer/sender/player_server.py`

### Receiver

- Create: `src/optical_transfer/receiver/ffmpeg_frames.py`
- Create: `src/optical_transfer/receiver/preprocess.py`
- Create: `src/optical_transfer/receiver/qr_decode.py`
- Create: `src/optical_transfer/receiver/collector.py`
- Create: `src/optical_transfer/receiver/reassemble.py`
- Create: `src/optical_transfer/receiver/report.py`
- Create: `src/optical_transfer/receiver/restore.py`

### Protocol

- Create: `src/optical_transfer/protocol/constants.py`
- Create: `src/optical_transfer/protocol/header.py`
- Create: `src/optical_transfer/protocol/types.py`
- Create: `src/optical_transfer/protocol/manifest_types.py`

### Web player

- Create: `web/player/index.html`
- Create: `web/player/player.js`
- Create: `web/player/player.css`

### Tests

- Create: `tests/conftest.py`
- Create: `tests/test_cli.py`
- Create: `tests/protocol/test_header.py`
- Create: `tests/sender/test_archive.py`
- Create: `tests/sender/test_chunker.py`
- Create: `tests/sender/test_crypto.py`
- Create: `tests/sender/test_manifest.py`
- Create: `tests/sender/test_packets.py`
- Create: `tests/receiver/test_collector.py`
- Create: `tests/receiver/test_reassemble.py`
- Create: `tests/receiver/test_restore.py`
- Create: `tests/integration/test_roundtrip_images.py`

### Project files

- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`

## Task 1: Bootstrap Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/optical_transfer/__init__.py`
- Create: `src/optical_transfer/cli.py`
- Create: `tests/test_cli.py`
- Create: `.gitignore`

- [ ] **Step 1: Write the failing CLI smoke test**

```python
from optical_transfer.cli import build_parser


def test_parser_exposes_send_and_receive_commands():
    parser = build_parser()
    subcommands = parser._subparsers._group_actions[0].choices
    assert "send" in subcommands
    assert "receive" in subcommands
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with import or symbol errors because the package and parser do not exist yet.

- [ ] **Step 3: Write the minimal project scaffold**

```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="optical-transfer")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("send")
    subparsers.add_parser("receive")
    return parser
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/optical_transfer/__init__.py src/optical_transfer/cli.py tests/test_cli.py
git commit -m "chore: bootstrap optical transfer cli"
```

## Task 2: Freeze Protocol Header Encoding

**Files:**
- Create: `src/optical_transfer/protocol/constants.py`
- Create: `src/optical_transfer/protocol/types.py`
- Create: `src/optical_transfer/protocol/header.py`
- Create: `tests/protocol/test_header.py`

- [ ] **Step 1: Write the failing protocol header tests**

```python
from optical_transfer.protocol.header import PacketHeader, encode_header, decode_header


def test_header_roundtrip_preserves_required_fields():
    header = PacketHeader(
        protocol_version=1,
        session_id=b"0123456789abcdef",
        packet_type=1,
        chunk_index=7,
        total_chunks=19,
        payload_length=1536,
        capability_flags=0,
    )
    encoded = encode_header(header)
    decoded = decode_header(encoded)
    assert decoded == header
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/protocol/test_header.py -v`
Expected: FAIL because protocol modules do not exist.

- [ ] **Step 3: Implement the header model and binary codec**

```python
@dataclass(frozen=True)
class PacketHeader:
    protocol_version: int
    session_id: bytes
    packet_type: int
    chunk_index: int
    total_chunks: int
    payload_length: int
    capability_flags: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/protocol/test_header.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/optical_transfer/protocol/constants.py src/optical_transfer/protocol/types.py src/optical_transfer/protocol/header.py tests/protocol/test_header.py
git commit -m "feat: add packet header codec"
```

## Task 3: Implement Archive and Manifest Creation

**Files:**
- Create: `src/optical_transfer/sender/archive.py`
- Create: `src/optical_transfer/sender/manifest.py`
- Create: `src/optical_transfer/protocol/manifest_types.py`
- Create: `tests/sender/test_archive.py`
- Create: `tests/sender/test_manifest.py`

- [ ] **Step 1: Write failing tests for tar.gz creation and manifest generation**

```python
def test_archive_directory_creates_tar_gz(tmp_path):
    ...


def test_manifest_contains_archive_hash_and_chunk_metadata(tmp_path):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sender/test_archive.py tests/sender/test_manifest.py -v`
Expected: FAIL because archive and manifest builders are missing.

- [ ] **Step 3: Implement archive builder and manifest serializer**

```python
def archive_directory(source_dir: Path, output_path: Path) -> ArchiveResult:
    ...


def build_manifest(archive_result: ArchiveResult, chunk_size: int, total_chunks: int) -> Manifest:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/sender/test_archive.py tests/sender/test_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/optical_transfer/sender/archive.py src/optical_transfer/sender/manifest.py src/optical_transfer/protocol/manifest_types.py tests/sender/test_archive.py tests/sender/test_manifest.py
git commit -m "feat: add archive and manifest generation"
```

## Task 4: Implement Chunking and Per-Chunk AEAD

**Files:**
- Create: `src/optical_transfer/sender/chunker.py`
- Create: `src/optical_transfer/sender/crypto.py`
- Create: `tests/sender/test_chunker.py`
- Create: `tests/sender/test_crypto.py`

- [ ] **Step 1: Write failing tests for chunk slicing and per-chunk authentication**

```python
def test_chunk_bytes_yields_stable_chunk_indexes():
    ...


def test_encrypt_chunk_roundtrip_succeeds_with_matching_password():
    ...


def test_encrypt_chunk_rejects_tampered_ciphertext():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sender/test_chunker.py tests/sender/test_crypto.py -v`
Expected: FAIL because chunker and crypto functions do not exist.

- [ ] **Step 3: Implement chunker and AEAD utilities**

```python
def chunk_bytes(data: bytes, chunk_size: int) -> list[Chunk]:
    ...


def encrypt_chunk(chunk: Chunk, password: str, session_id: bytes, salt: bytes) -> EncryptedChunk:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/sender/test_chunker.py tests/sender/test_crypto.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/optical_transfer/sender/chunker.py src/optical_transfer/sender/crypto.py tests/sender/test_chunker.py tests/sender/test_crypto.py
git commit -m "feat: add chunking and authenticated encryption"
```

## Task 5: Build Packet Assembly and Image-Based Sender Roundtrip

**Files:**
- Create: `src/optical_transfer/sender/packets.py`
- Create: `src/optical_transfer/sender/session.py`
- Create: `src/optical_transfer/sender/qr_payloads.py`
- Create: `tests/sender/test_packets.py`
- Create: `tests/integration/test_roundtrip_images.py`

- [ ] **Step 1: Write failing tests for packet assembly and image-based roundtrip**

```python
def test_build_data_packet_wraps_header_and_ciphertext():
    ...


def test_image_based_roundtrip_restores_archive_without_video(tmp_path):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sender/test_packets.py tests/integration/test_roundtrip_images.py -v`
Expected: FAIL because packet assembly and QR payload generation are not implemented.

- [ ] **Step 3: Implement packet builder and QR payload helpers**

```python
def build_data_packet(header: PacketHeader, ciphertext: bytes) -> bytes:
    ...


def build_session_payloads(source_dir: Path, password: str, chunk_size: int) -> SessionPayloadSet:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/sender/test_packets.py tests/integration/test_roundtrip_images.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/optical_transfer/sender/packets.py src/optical_transfer/sender/session.py src/optical_transfer/sender/qr_payloads.py tests/sender/test_packets.py tests/integration/test_roundtrip_images.py
git commit -m "feat: assemble authenticated qr payloads"
```

## Task 6: Add Local Player Server and Sender CLI

**Files:**
- Create: `src/optical_transfer/config.py`
- Create: `src/optical_transfer/sender/player_server.py`
- Create: `web/player/index.html`
- Create: `web/player/player.js`
- Create: `web/player/player.css`
- Modify: `src/optical_transfer/cli.py`

- [ ] **Step 1: Write failing tests for sender CLI config and player payload serving**

```python
def test_send_command_builds_default_sender_config():
    ...


def test_player_server_exposes_packet_sequence_json(tmp_path):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL because sender configuration and player serving logic are incomplete.

- [ ] **Step 3: Implement sender config, local server, and web player**

```python
def handle_send(args: argparse.Namespace) -> int:
    ...


def create_player_app(payloads: SessionPayloadSet) -> HTTPServer:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/optical_transfer/config.py src/optical_transfer/cli.py src/optical_transfer/sender/player_server.py web/player/index.html web/player/player.js web/player/player.css tests/test_cli.py
git commit -m "feat: add sender cli and local web player"
```

## Task 7: Implement Receiver Collect, Reassemble, and Restore

**Files:**
- Create: `src/optical_transfer/receiver/collector.py`
- Create: `src/optical_transfer/receiver/reassemble.py`
- Create: `src/optical_transfer/receiver/restore.py`
- Create: `tests/receiver/test_collector.py`
- Create: `tests/receiver/test_reassemble.py`
- Create: `tests/receiver/test_restore.py`

- [ ] **Step 1: Write failing tests for dedupe, completion, and restore semantics**

```python
def test_collector_deduplicates_chunks_by_session_and_index():
    ...


def test_reassembler_requires_complete_logical_chunk_set():
    ...


def test_restore_archive_extracts_into_fresh_directory(tmp_path):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/receiver/test_collector.py tests/receiver/test_reassemble.py tests/receiver/test_restore.py -v`
Expected: FAIL because receiver collector and restore pipeline are missing.

- [ ] **Step 3: Implement collector, strict completion checks, and restore logic**

```python
class PacketCollector:
    ...


def reassemble_archive(chunks: list[VerifiedChunk], expected_total: int) -> bytes:
    ...


def restore_archive_bytes(archive_bytes: bytes, output_root: Path) -> Path:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/receiver/test_collector.py tests/receiver/test_reassemble.py tests/receiver/test_restore.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/optical_transfer/receiver/collector.py src/optical_transfer/receiver/reassemble.py src/optical_transfer/receiver/restore.py tests/receiver/test_collector.py tests/receiver/test_reassemble.py tests/receiver/test_restore.py
git commit -m "feat: add receiver collection and restore pipeline"
```

## Task 8: Add Video Frame Extraction, Preprocessing, and QR Decode

**Files:**
- Create: `src/optical_transfer/receiver/ffmpeg_frames.py`
- Create: `src/optical_transfer/receiver/preprocess.py`
- Create: `src/optical_transfer/receiver/qr_decode.py`
- Modify: `tests/integration/test_roundtrip_images.py`

- [ ] **Step 1: Write failing tests around frame extraction and decode interfaces**

```python
def test_ffmpeg_command_builder_uses_expected_frame_output_pattern():
    ...


def test_preprocess_returns_decoder_ready_image(tmp_path):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_roundtrip_images.py -v`
Expected: FAIL because video and preprocess helpers do not exist yet.

- [ ] **Step 3: Implement frame extraction, preprocessing, and decode adapters**

```python
def extract_frames(video_path: Path, output_dir: Path) -> list[Path]:
    ...


def preprocess_frame(frame_path: Path) -> np.ndarray:
    ...


def decode_qr_payload(image: np.ndarray) -> bytes | None:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_roundtrip_images.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/optical_transfer/receiver/ffmpeg_frames.py src/optical_transfer/receiver/preprocess.py src/optical_transfer/receiver/qr_decode.py tests/integration/test_roundtrip_images.py
git commit -m "feat: add video extraction and qr decoding adapters"
```

## Task 9: Wire Full Receiver CLI and Session Report

**Files:**
- Create: `src/optical_transfer/receiver/report.py`
- Modify: `src/optical_transfer/cli.py`
- Create: `README.md`

- [ ] **Step 1: Write failing tests for receiver CLI orchestration and report output**

```python
def test_receive_command_accepts_multiple_videos():
    ...


def test_session_report_includes_required_summary_fields():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL because receive orchestration and reporting are incomplete.

- [ ] **Step 3: Implement receive command orchestration and report rendering**

```python
def handle_receive(args: argparse.Namespace) -> int:
    ...


def build_session_report(stats: SessionStats) -> str:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/optical_transfer/cli.py src/optical_transfer/receiver/report.py README.md tests/test_cli.py
git commit -m "feat: add receiver cli and session reporting"
```

## Task 10: Verify End-to-End and Document Manual Validation

**Files:**
- Modify: `README.md`
- Modify: `tests/integration/test_roundtrip_images.py`

- [ ] **Step 1: Add a final integration test that exercises the happy path without video**

```python
def test_end_to_end_roundtrip_restores_original_files(tmp_path):
    ...
```

- [ ] **Step 2: Run the full automated test suite**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 3: Run manual validation for the first real-world pipeline**

Run: `python -m optical_transfer.cli send /path/to/sample_dir`
Expected: local player starts and serves a deterministic QR sequence in Chromium

Run: `python -m optical_transfer.cli receive recording1.mp4 recording2.mp4`
Expected: receiver emits a session report and restores the archive into a fresh directory when enough chunks are recovered

- [ ] **Step 4: Update README with install and validation instructions**

```markdown
## Manual Validation

1. Install native dependencies
2. Run `send`
3. Record video
4. Run `receive`
```

- [ ] **Step 5: Commit**

```bash
git add README.md tests/integration/test_roundtrip_images.py
git commit -m "docs: add validation workflow for optical transfer v1"
```
