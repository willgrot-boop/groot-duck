#!/bin/sh
set -eu
cd "$(dirname "$0")"
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/microduck-native.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT HUP INT TERM
"${CXX:-g++}" -std=c++17 -Wall -Wextra -Werror -pedantic -Iinclude \
  test/test_safety.cpp -o "$build_dir/test_safety"
"$build_dir/test_safety"
