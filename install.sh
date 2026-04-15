#!/usr/bin/env bash
set -euo pipefail

if ! command -v pipx >/dev/null 2>&1; then
    echo "Error: pipx is not installed." >&2
    echo "Install it with one of:" >&2
    echo "  brew install pipx && pipx ensurepath" >&2
    echo "  python3 -m pip install --user pipx && python3 -m pipx ensurepath" >&2
    exit 1
fi

cd "$(dirname "$0")"
pipx install . --force
