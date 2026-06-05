#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-foo"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Initializing foo environment in ${VENV_DIR}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} not found in PATH" >&2
  exit 1
fi

if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "error: ${PYTHON_BIN} must be Python 3.9 or newer (project requires >=3.9)" >&2
  echo "hint: set PYTHON_BIN to a newer interpreter, for example:" >&2
  echo '  PYTHON_BIN=python3.9 ./scripts/setup-foo-macos.sh' >&2
  exit 1
fi

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .

cat <<EOF
Foo environment is ready.

Activate it with:
  source "${VENV_DIR}/bin/activate"

Run foo with:
  atlasx foo --source ./payload --password "secret"

Notes:
  - a browser is optional and only needed for --open-browser
  - the foo now renders real QR frames via the packaged qrcode dependency
EOF
