#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
mkdir -p "$BUILD_DIR/test-results"
python3 "$PROJECT_ROOT/tests/make_fixture.py" "$BUILD_DIR/synthetic-fadt.bin"
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) EXE_SUFFIX=.exe ;;
    *) EXE_SUFFIX= ;;
esac
TEST_BIN="$BUILD_DIR/core_tests$EXE_SUFFIX"
"${CC:-gcc}" -std=c11 -O2 -Wall -Wextra -Werror -I"$PROJECT_ROOT/src" \
    "$PROJECT_ROOT/tests/core_tests.c" -o "$TEST_BIN"
"$TEST_BIN" "$BUILD_DIR/synthetic-fadt.bin" | tee "$BUILD_DIR/test-results/core-tests.txt"
