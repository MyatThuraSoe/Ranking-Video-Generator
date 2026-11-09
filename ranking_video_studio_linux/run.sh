#!/usr/bin/env bash
# Run LRBar-RankGen from source (development).
set -eu
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" main.py "$@"
