# AtlasX

`atlasx` is a CLI for moving a directory through a QR video stream.

Detailed usage is documented in [docs/atlasx-usage-manual.md](/Users/taissa/lushuai/code/personal/mproject/docs/atlasx-usage-manual.md).

## Setup

The project is developed against Python 3.9+.

1. Create and activate a virtual environment.
2. Install the package in editable mode: `pip install -e .`
3. Install or verify the native tools used by the runtime:
   - `ffmpeg` for bar frame extraction
4. If you want the foo to open a browser for you, make sure a default browser is available on the machine.
5. If you are running outside the prepared development environment, install the Python runtime dependencies used by the pipeline: `Pillow`, `numpy`, `cryptography`, `opencv-python`, `qrcode`, and a QR decoder such as `pyzbar` or a ZXing-backed binding.
6. On macOS, the bar setup script defaults to the public PyPI index so `opencv-python` can install from a wheel instead of building from source.

## Requirements

- Python 3.9+
- `ffmpeg`
- A browser is optional and only needed if you use `foo --open-browser`
- The Python packages listed above if they are not already present in your environment

## Foo

The foo packages a single directory, encrypts chunk payloads, and starts a local preview server that serves the looping QR frames.

```bash
atlasx foo --source ./payload --password "secret"
```

Useful options:

- `--chunk-size` to tune QR payload density; the default is `2048` bytes
- `--player-host` and `--player-port` to control the local preview server
- `--open-browser` to ask the foo to launch the preview URL in your default browser

## Bar

The bar accepts one or more recorded videos, extracts frames with `ffmpeg`, decodes QR payloads, reconstructs the archive, and restores it into a fresh directory under the chosen output root.

New transfers use independently recoverable bundle chunks. If some QR frames are
missing, bar still restores every complete file it can verify and writes received
segments of incomplete files under `.atlasx-partial`; saved progress can later be
completed with a missing-chunk playback. Legacy `tar.gz` sessions remain readable
but still require their full chunk set.

```bash
atlasx bar recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```

The bar prints a session report with:

- input video count
- extracted frame count
- decoded frame count
- packet and chunk counts
- authentication failures
- archive hash result
- per-stage timing

## Notes

- The current implementation expects foo and bar to use the same password.
- `bar` works offline, saves verified progress under the output root, and can merge packets recovered from multiple recordings of the same session.
- Restored files are extracted into a fresh directory so repeated runs do not overwrite the original output root.

## Manual Validation

1. Pick a sample directory with a small amount of real content.
2. Run the foo:

```bash
atlasx foo --source ./payload --password "secret"
```

3. Record the browser window from a phone or camera while the QR preview is looping.
4. Run the bar on one or more recordings:

```bash
atlasx bar recording1.mp4 recording2.mp4 --password "secret" --output-root restored
```

5. Confirm the session report shows a `match` hash result and inspect the restored directory created under the output root.
