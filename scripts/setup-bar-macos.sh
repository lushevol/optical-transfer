#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-bar"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"

echo "Initializing bar environment in ${VENV_DIR}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} not found in PATH" >&2
  exit 1
fi

if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "error: ${PYTHON_BIN} must be Python 3.9 or newer (project requires >=3.9)" >&2
  echo "hint: set PYTHON_BIN to a newer interpreter, for example:" >&2
  echo '  PYTHON_BIN=python3.9 ./scripts/setup-bar-macos.sh' >&2
  exit 1
fi

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade --index-url "${PIP_INDEX_URL}" pip setuptools wheel qrcode
python -m pip install --index-url "${PIP_INDEX_URL}" --only-binary=opencv-python -e '.[bar]'

if ! command -v ffmpeg >/dev/null 2>&1; then
  cat <<EOF
warning: ffmpeg was not found in PATH.

Install it before running bar. For example on macOS with Homebrew:
  brew install ffmpeg
EOF
  exit 1
fi

cat <<EOF
Bar environment is ready.

Activate it with:
  source "${VENV_DIR}/bin/activate"

Verify ffmpeg:
  ffmpeg -version

Run bar with:
  atlasx bar recording.mp4 --password "secret" --output-root restored

Notes:
  - the bar now depends on the packaged OpenCV QR decoder runtime
EOF
