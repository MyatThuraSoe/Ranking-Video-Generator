#!/usr/bin/env bash
# Build the LRBar-License-Manager jar (Linux/macOS). Mirrors build.bat.
set -eu
cd "$(dirname "$0")"

mkdir -p build/classes
javac -encoding UTF-8 -d build/classes src/lrbar/license/*.java

mkdir -p dist
JAR_TOOL=jar
if ! command -v jar >/dev/null 2>&1; then
    # Some JDKs ship no jar tool on PATH; derive it from java.home.
    JH="$(java -XshowSettings:properties -version 2>&1 \
        | awk -F' = ' '$1 ~ /java\.home$/ { print $2; exit }')"
    JH="$(printf '%s' "$JH" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    if [ -n "$JH" ] && [ -x "$JH/bin/jar" ]; then
        JAR_TOOL="$JH/bin/jar"
    fi
fi

"$JAR_TOOL" --create --file dist/LRBar-License-Manager.jar \
    --main-class lrbar.license.Main -C build/classes .
echo "Built $(cd dist && pwd)/LRBar-License-Manager.jar"
