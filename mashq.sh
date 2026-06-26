#!/usr/bin/env bash
# Wrapper for mashq.py - run the CLI through this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/mashq.py" "$@"
