# Optical Transfer Usage Manual

## Overview

`optical-transfer` is a CLI for moving one directory over a one-way optical link:

- sender: directory -> archive -> encrypted packets -> QR frame sequence
- receiver: recorded video(s) -> extracted frames -> decoded packets -> restored directory

The current implementation is designed for:

- one directory per transfer
- offline receive from one or more recorded videos
- sender preview through a local HTTP server
- password-protected transfers

## Environment

Required:

- Python 3.9+
- project Python dependencies installed in the active environment
- `ffmpeg` available in `PATH` for receiver frame extraction

Optional:

- a default browser, only if you want `send --open-browser`

Install the project in editable mode:

```bash
pip install -e .
```

Verify `ffmpeg`:

```bash
ffmpeg -version
```

## Environment Initialization Scripts

Two macOS setup scripts are provided so sender and receiver can be initialized separately:

```bash
./scripts/setup-sender-macos.sh
./scripts/setup-receiver-macos.sh
```

Behavior:

- `setup-sender-macos.sh`
  Creates `.venv-sender`, installs the project, and prepares a sender-only environment.
- `setup-receiver-macos.sh`
  Creates `.venv-receiver`, installs the project, and checks that `ffmpeg` is available.

Both scripts:

- use `python3` by default
- can be pointed at another interpreter with `PYTHON_BIN=/path/to/python`
- do not modify your shell profile

## Quick Start

Send:

```bash
optical-transfer send --source ./payload --password "secret"
```

Receive:

```bash
optical-transfer receive recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```

The sender prints a local preview URL. Open that URL on the sender machine, keep the QR preview visible, record it, then run `receive` with the recorded video files.

## Sender

Basic usage:

```bash
optical-transfer send --source ./payload --password "secret"
```

Useful options:

- `--source`: source directory to transmit. Default: current directory.
- `--password`: shared password used by sender and receiver.
- `--chunk-size`: packet payload size before encryption. Default: `64`.
- `--frame-interval-ms`: time each QR frame remains on screen. Default: `600`.
- `--player-host`: bind address for the local preview server. Default: `127.0.0.1`.
- `--player-port`: bind port for the local preview server. Default: `8765`.
- `--open-browser`: ask the sender to open the preview URL in the default browser.

Example with explicit browser launch:

```bash
optical-transfer send \
  --source ./payload \
  --password "secret" \
  --frame-interval-ms 450 \
  --open-browser
```

Notes:

- if `--open-browser` is not set, sender still starts normally and prints the preview URL
- sender keeps running until interrupted
- sender currently assumes IPv4 for the preview server

## Receiver

Basic usage:

```bash
optical-transfer receive recording1.mp4 --password "secret" --output-root restored
```

Multiple recordings from the same session can be provided:

```bash
optical-transfer receive \
  recording1.mp4 \
  recording2.mp4 \
  recording3.mp4 \
  --password "secret" \
  --output-root restored
```

Useful options:

- `videos`: one or more video files for the same transfer session
- `--password`: shared password used during send
- `--output-root`: parent directory for restored output. Default: `restored`

Notes:

- receiver restores into a fresh subdirectory under `--output-root`
- receiver does not overwrite an existing restored directory
- receiver expects all input videos to belong to the same session

## Session Report

On success, receiver prints a session report similar to:

```text
input video count: 1
total extracted frame count: 23
successfully decoded frame count: 23
raw packet count: 23
deduplicated valid chunk count: 22
missing chunk count: 0
authentication failure count: 0
final archive hash result: match
restored directory: /path/to/restored/restored-xxxx
per-stage timing:
  extract_frames: 0.152s
  preprocess_decode: 0.101s
  reassemble: 0.000s
  restore: 0.001s
```

Interpretation:

- `raw packet count` includes all valid packet decodes, including repeated packets
- `deduplicated valid chunk count` counts unique data chunks only
- `missing chunk count: 0` plus `final archive hash result: match` indicates a successful recovery

## Recommended Workflow

1. Prepare a small test directory.
2. Run `send`.
3. Open the printed preview URL if the browser was not opened automatically.
4. Record the QR preview on another device.
5. Transfer the recorded video back to the receiver machine.
6. Run `receive`.
7. Confirm the report shows `match`.
8. Inspect the restored directory.

## Current Defaults

These defaults are intentionally conservative:

- `chunk_size = 64`
- `frame_interval_ms = 600`

The current sender preview renders:

- fixed-size QR frames
- even-dimension frame canvases for video encoder compatibility
- browser-friendly PNG data URLs served from the local preview server

## Troubleshooting

`ffmpeg: command not found`

- install `ffmpeg`
- verify it is visible in `PATH`

`Preview URL` is printed but nothing opens

- this is normal when `--open-browser` is not set
- open the printed URL manually in a browser

Receiver says `missing required chunks`

- the recording did not yield enough decodable frames
- record a longer clip
- try multiple recordings from the same session
- reduce `--chunk-size`
- increase `--frame-interval-ms`

Receiver fails with password or authentication errors

- confirm sender and receiver used the same password

Video encoding fails on generated frames

- use the built-in sender preview rather than ad hoc frame generation
- current implementation already normalizes frame size for common video encoders

## Limits

Current implementation does not yet provide:

- FEC
- multi-directory transfers in one session
- real-time receive
- sender-side duration estimation

## Reference Commands

Install:

```bash
pip install -e .
```

Send with defaults:

```bash
optical-transfer send --source ./payload --password "secret"
```

Send with explicit browser launch and faster playback:

```bash
optical-transfer send \
  --source ./payload \
  --password "secret" \
  --frame-interval-ms 450 \
  --open-browser
```

Receive one video:

```bash
optical-transfer receive recording.mp4 --password "secret" --output-root restored
```

Receive multiple videos for one session:

```bash
optical-transfer receive recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```
