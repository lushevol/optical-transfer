#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-sender"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Initializing sender environment in ${VENV_DIR}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} not found in PATH" >&2
  exit 1
fi

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .

cat <<EOF
Sender environment is ready.

Activate it with:
  source "${VENV_DIR}/bin/activate"

Run sender with:
  optical-transfer send --source ./payload --password "secret"

Notes:
  - a browser is optional and only needed for --open-browser
EOF
