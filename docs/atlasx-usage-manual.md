# AtlasX Usage Manual

## Overview

`atlasx` is a CLI for moving one directory over a one-way QR link:

- foo: directory -> archive -> encrypted packets -> QR frame sequence
- bar: recorded video(s) -> extracted frames -> decoded packets -> restored directory

The current implementation is designed for:

- one directory per transfer
- offline bar from one or more recorded videos
- foo preview through a local HTTP server
- password-protected transfers

## Environment

Required:

- Python 3.9+
- project Python dependencies installed in the active environment
- `ffmpeg` available in `PATH` for bar frame extraction

Optional:

- a default browser, only if you want `foo --open-browser`

Install the project in editable mode:

```bash
pip install -e .
```

Verify `ffmpeg`:

```bash
ffmpeg -version
```

## Environment Initialization Scripts

Two macOS setup scripts are provided so foo and bar can be initialized separately:

```bash
./scripts/setup-foo-macos.sh
./scripts/setup-bar-macos.sh
```

Behavior:

- `setup-foo-macos.sh`
  Creates `.venv-foo`, installs the project, and prepares a foo-only environment.
- `setup-bar-macos.sh`
  Creates `.venv-bar`, installs the project, and checks that `ffmpeg` is available.

Both scripts:

- use `python3` by default
- can be pointed at another interpreter with `PYTHON_BIN=/path/to/python`
- do not modify your shell profile
- bar setup defaults to the public PyPI index so `opencv-python` installs from a wheel instead of a source build when possible

## Quick Start

Foo:

```bash
atlasx foo --source ./payload --password "secret"
```

Bar:

```bash
atlasx bar recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```

The foo prints a local preview URL. Open that URL on the foo machine, keep the QR preview visible, record it, then run `bar` with the recorded video files.

## Foo

Basic usage:

```bash
atlasx foo --source ./payload --password "secret"
```

Useful options:

- `--source`: source directory to transmit. Default: current directory.
- `--password`: shared password used by foo and bar.
- `--chunk-size`: packet payload size before encryption. Default: `2048`.
- `--frame-interval-ms`: time each QR frame remains on screen. Default: `600`.
- `--player-host`: bind address for the local preview server. Default: `127.0.0.1`.
- `--player-port`: bind port for the local preview server. Default: `8765`.
- `--open-browser`: ask the foo to open the preview URL in the default browser.

Example with explicit browser launch:

```bash
atlasx foo \
  --source ./payload \
  --password "secret" \
  --frame-interval-ms 450 \
  --open-browser
```

Notes:

- if `--open-browser` is not set, foo still starts normally and prints the preview URL
- foo keeps running until interrupted
- foo currently assumes IPv4 for the preview server

## Bar

Basic usage:

```bash
atlasx bar recording1.mp4 --password "secret" --output-root restored
```

Multiple recordings from the same session can be provided:

```bash
atlasx bar \
  recording1.mp4 \
  recording2.mp4 \
  recording3.mp4 \
  --password "secret" \
  --output-root restored
```

Useful options:

- `videos`: one or more video files for the same transfer session
- `--password`: shared password used during foo
- `--output-root`: parent directory for restored output. Default: `restored`

Notes:

- bar restores into a fresh subdirectory under `--output-root`
- bar does not overwrite an existing restored directory
- bar expects all input videos to belong to the same session
- bar saves verified encrypted packets under `.atlasx-progress` in the output root, so a later run with the same `--output-root` can resume from prior recordings

## Session Report

On success, bar prints a session report similar to:

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
2. Run `foo`.
3. Open the printed preview URL if the browser was not opened automatically.
4. Record the QR preview on another device.
5. Transfer the recorded video back to the bar machine.
6. Run `bar`.
7. Confirm the report shows `match`.
8. Inspect the restored directory.

## Current Defaults

These defaults favor shorter recordings while leaving margin under the QR capacity used by the player:

- `chunk_size = 2048`
- `frame_interval_ms = 600`

The current foo preview renders:

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

Bar says `missing required chunks`

- the recording did not yield enough decodable frames
- record a longer clip and rerun bar with the same `--output-root` so saved progress is reused
- try multiple recordings from the same session
- reduce `--chunk-size`
- increase `--frame-interval-ms`

Bar fails with password or authentication errors

- confirm foo and bar used the same password

Video encoding fails on generated frames

- use the built-in foo preview rather than ad hoc frame generation
- current implementation already normalizes frame size for common video encoders

## Limits

Current implementation does not yet provide:

- FEC
- multi-directory transfers in one session
- real-time bar
- foo-side duration estimation

## Reference Commands

Install:

```bash
pip install -e .
```

Foo with defaults:

```bash
atlasx foo --source ./payload --password "secret"
```

Foo with explicit browser launch and faster playback:

```bash
atlasx foo \
  --source ./payload \
  --password "secret" \
  --frame-interval-ms 450 \
  --open-browser
```

Bar one video:

```bash
atlasx bar recording.mp4 --password "secret" --output-root restored
```

Bar multiple videos for one session:

```bash
atlasx bar recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```
