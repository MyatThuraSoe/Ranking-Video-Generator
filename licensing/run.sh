#!/usr/bin/env bash
# GUI launcher for the owner's License Manager (Linux/macOS).
# Mirrors "Run License Manager.bat" for non-Windows machines.
set -eu
cd "$(dirname "$0")"

if [ ! -f java/dist/LRBar-License-Manager.jar ]; then
    bash java/build.sh
fi
exec java -jar java/dist/LRBar-License-Manager.jar "$@"
