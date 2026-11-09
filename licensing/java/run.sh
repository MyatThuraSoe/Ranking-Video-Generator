#!/usr/bin/env bash
# Open the License Manager GUI (Linux/macOS), or issue a key via the CLI.
#
#   ./run.sh                       # graphical window
#   ./run.sh --machine 7F3A-... --type lifetime   # CLI, same options as the jar
set -eu
cd "$(dirname "$0")"

if [ ! -f dist/LRBar-License-Manager.jar ]; then
    bash build.sh
fi
exec java -jar dist/LRBar-License-Manager.jar "$@"
