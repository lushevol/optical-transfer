# Optical Transfer

`optical-transfer` is a CLI for moving a directory through an optical QR video stream.

## Setup

The project is developed against Python 3.12.

1. Create and activate a virtual environment.
2. Install the package in editable mode: `pip install -e .`
3. Install or verify the native tools used by the runtime:
   - `ffmpeg` for receiver frame extraction
   - `Chrome` or `Chromium` for the sender preview player
4. If you are running outside the prepared development environment, install the Python runtime dependencies used by the pipeline: `Pillow`, `numpy`, `cryptography`, `opencv-python`, `qrcode`, and a QR decoder such as `pyzbar` or a ZXing-backed binding.

## Requirements

- Python 3.12+
- `ffmpeg`
- `Chrome` or `Chromium`
- The Python packages listed above if they are not already present in your environment

## Sender

The sender packages a single directory, encrypts chunk payloads, and opens a local preview page that loops QR frames in the browser.

```bash
optical-transfer send --source ./payload --password "secret"
```

Useful options:

- `--chunk-size` to tune QR payload density
- `--player-host` and `--player-port` to control the local preview server

## Receiver

The receiver accepts one or more recorded videos, extracts frames with `ffmpeg`, decodes QR payloads, reconstructs the archive, and restores it into a fresh directory under the chosen output root.

```bash
optical-transfer receive recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```

The receiver prints a session report with:

- input video count
- extracted frame count
- decoded frame count
- packet and chunk counts
- authentication failures
- archive hash result
- per-stage timing

## Notes

- The current implementation expects sender and receiver to use the same password.
- `receive` works offline and can merge packets recovered from multiple recordings of the same session.
- Restored files are extracted into a fresh directory so repeated runs do not overwrite the original output root.

## Manual Validation

1. Pick a sample directory with a small amount of real content.
2. Run the sender:

```bash
optical-transfer send --source ./payload --password "secret"
```

3. Record the browser window from a phone or camera while the QR preview is looping.
4. Run the receiver on one or more recordings:

```bash
optical-transfer receive recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```

5. Confirm the session report shows a `match` hash result and inspect the restored directory created under the output root.
