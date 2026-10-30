#!/usr/bin/env bash
# Activate the project's development venv first. No Node or minifier is used.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ "${1:-}" == "--check" ]]; then
    python -m ruff format --check .
    python -m ruff check .
    python -m djlint app/templates --check --quiet
    python -m djlint app/templates --extension xml --check --quiet
    python scripts/format_assets.py --check
elif [[ $# -eq 0 ]]; then
    python -m ruff format .
    python -m ruff check .
    # djLint returns 1 when it rewrites files; a check distinguishes success from errors.
    python -m djlint app/templates --reformat --quiet || \
        python -m djlint app/templates --check --quiet
    python -m djlint app/templates --extension xml --reformat --quiet || \
        python -m djlint app/templates --extension xml --check --quiet
    python scripts/format_assets.py
else
    printf 'Usage: scripts/format.sh [--check]\n' >&2
    exit 2
fi
