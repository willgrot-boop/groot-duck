#!/bin/sh
set -eu
cd "$(dirname "$0")"
json_include=${ARDUINOJSON_INCLUDE_DIR:-.pio/libdeps/esp32dev/ArduinoJson/src}
if [ ! -f "$json_include/ArduinoJson.h" ]; then
  echo "ArduinoJson 7.3.1 headers required: set ARDUINOJSON_INCLUDE_DIR or install pinned PlatformIO dependencies." >&2
  exit 2
fi
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/microduck-protocol.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT HUP INT TERM
"${CXX:-g++}" -std=c++17 -Wall -Wextra -Werror -pedantic \
  -Iinclude -I"$json_include" test/test_protocol.cpp -o "$build_dir/test_protocol"
"$build_dir/test_protocol"
