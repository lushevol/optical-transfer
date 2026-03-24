# Optical Transfer

`optical-transfer` is a CLI for moving a directory through an optical QR video stream.

## Requirements

- Python 3.12+
- `ffmpeg` for receiver frame extraction
- `Chrome` or `Chromium` for the sender preview player
- Python packages from the project environment, including `Pillow`, `numpy`, and `cryptography`

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
