#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-receiver"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Initializing receiver environment in ${VENV_DIR}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} not found in PATH" >&2
  exit 1
fi

if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "error: ${PYTHON_BIN} must be Python 3.9 or newer (project requires >=3.9)" >&2
  echo "hint: set PYTHON_BIN to a newer interpreter, for example:" >&2
  echo '  PYTHON_BIN=python3.9 ./scripts/setup-receiver-macos.sh' >&2
  exit 1
fi

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[receiver]'

if ! command -v ffmpeg >/dev/null 2>&1; then
  cat <<EOF
warning: ffmpeg was not found in PATH.

Install it before running receiver. For example on macOS with Homebrew:
  brew install ffmpeg
EOF
  exit 1
fi

cat <<EOF
Receiver environment is ready.

Activate it with:
  source "${VENV_DIR}/bin/activate"

Verify ffmpeg:
  ffmpeg -version

Run receiver with:
  optical-transfer receive recording.mp4 --password "secret" --output-root restored

Notes:
  - the receiver now depends on the packaged OpenCV QR decoder runtime
EOF
