# AtlasX Usage Manual

## Overview

`atlasx` is a CLI for moving one directory over a one-way QR link:

- outbound: directory -> archive -> encrypted packets -> QR frame sequence
- inbound: recorded video(s) -> extracted frames -> decoded packets -> restored directory

The current implementation is designed for:

- one directory per transfer
- offline inbound from one or more recorded videos
- outbound preview through a local HTTP server
- password-protected transfers

## Environment

Required:

- Python 3.9+
- project Python dependencies installed in the active environment
- `ffmpeg` available in `PATH` for inbound frame extraction

Optional:

- a default browser, only if you want `outbound --open-browser`

Install the project in editable mode:

```bash
pip install -e .
```

Verify `ffmpeg`:

```bash
ffmpeg -version
```

## Environment Initialization Scripts

Two macOS setup scripts are provided so outbound and inbound can be initialized separately:

```bash
./scripts/setup-outbound-macos.sh
./scripts/setup-inbound-macos.sh
```

Behavior:

- `setup-outbound-macos.sh`
  Creates `.venv-outbound`, installs the project, and prepares a outbound-only environment.
- `setup-inbound-macos.sh`
  Creates `.venv-inbound`, installs the project, and checks that `ffmpeg` is available.

Both scripts:

- use `python3` by default
- can be pointed at another interpreter with `PYTHON_BIN=/path/to/python`
- do not modify your shell profile
- inbound setup defaults to the public PyPI index so `opencv-python` installs from a wheel instead of a source build when possible

## Quick Start

Outbound:

```bash
atlasx outbound --source ./payload --password "secret"
```

Inbound:

```bash
atlasx inbound recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```

The outbound prints a local preview URL. Open that URL on the outbound machine, keep the QR preview visible, record it, then run `inbound` with the recorded video files.

## Outbound

Basic usage:

```bash
atlasx outbound --source ./payload --password "secret"
```

Useful options:

- `--source`: source directory to transmit. Default: current directory.
- `--password`: shared password used by outbound and inbound.
- `--chunk-size`: packet payload size before encryption. Default: `2048`.
- `--frame-interval-ms`: time each QR frame remains on screen. Default: `600`.
- `--player-host`: bind address for the local preview server. Default: `127.0.0.1`.
- `--player-port`: bind port for the local preview server. Default: `8765`.
- `--open-browser`: ask the outbound to open the preview URL in the default browser.

Example with explicit browser launch:

```bash
atlasx outbound \
  --source ./payload \
  --password "secret" \
  --frame-interval-ms 450 \
  --open-browser
```

Notes:

- if `--open-browser` is not set, outbound still starts normally and prints the preview URL
- outbound keeps running until interrupted
- outbound currently assumes IPv4 for the preview server

## Inbound

Basic usage:

```bash
atlasx inbound recording1.mp4 --password "secret" --output-root restored
```

Multiple recordings from the same session can be provided:

```bash
atlasx inbound \
  recording1.mp4 \
  recording2.mp4 \
  recording3.mp4 \
  --password "secret" \
  --output-root restored
```

Useful options:

- `videos`: one or more video files for the same transfer session
- `--password`: shared password used during outbound
- `--output-root`: parent directory for restored output. Default: `restored`

Notes:

- inbound restores into a fresh subdirectory under `--output-root`
- inbound does not overwrite an existing restored directory
- inbound expects all input videos to belong to the same session
- inbound saves verified encrypted packets under `.atlasx-progress` in the output root, so a later run with the same `--output-root` can resume from prior recordings

## Session Report

On success, inbound prints a session report similar to:

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
2. Run `outbound`.
3. Open the printed preview URL if the browser was not opened automatically.
4. Record the QR preview on another device.
5. Transfer the recorded video back to the inbound machine.
6. Run `inbound`.
7. Confirm the report shows `match`.
8. Inspect the restored directory.

## Current Defaults

These defaults favor shorter recordings while leaving margin under the QR capacity used by the player:

- `chunk_size = 2048`
- `frame_interval_ms = 600`

The current outbound preview renders:

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

Inbound says `missing required chunks`

- the recording did not yield enough decodable frames
- record a longer clip and rerun inbound with the same `--output-root` so saved progress is reused
- try multiple recordings from the same session
- reduce `--chunk-size`
- increase `--frame-interval-ms`

Inbound fails with password or authentication errors

- confirm outbound and inbound used the same password

Video encoding fails on generated frames

- use the built-in outbound preview rather than ad hoc frame generation
- current implementation already normalizes frame size for common video encoders

## Limits

Current implementation does not yet provide:

- FEC
- multi-directory transfers in one session
- real-time inbound
- outbound-side duration estimation

## Reference Commands

Install:

```bash
pip install -e .
```

Outbound with defaults:

```bash
atlasx outbound --source ./payload --password "secret"
```

Outbound with explicit browser launch and faster playback:

```bash
atlasx outbound \
  --source ./payload \
  --password "secret" \
  --frame-interval-ms 450 \
  --open-browser
```

Inbound one video:

```bash
atlasx inbound recording.mp4 --password "secret" --output-root restored
```

Inbound multiple videos for one session:

```bash
atlasx inbound recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```
