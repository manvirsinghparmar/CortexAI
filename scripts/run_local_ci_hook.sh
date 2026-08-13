#!/bin/sh
set -eu

if [ -n "${CORTEX_CI_PYTHON:-}" ]; then
  cortex_python="$CORTEX_CI_PYTHON"
elif [ -x "venv/Scripts/python.exe" ]; then
  cortex_python="venv/Scripts/python.exe"
elif [ -x ".venv/Scripts/python.exe" ]; then
  cortex_python=".venv/Scripts/python.exe"
elif [ -x "venv/bin/python" ]; then
  cortex_python="venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
  cortex_python=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  cortex_python="$(command -v python3)"
else
  echo "CortexAI local CI gate could not find Python." >&2
  echo "Create venv/.venv or set CORTEX_CI_PYTHON to the project interpreter." >&2
  exit 1
fi

exec "$cortex_python" scripts/run_local_ci.py "$@"
