#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Synthetic tests only; no firmware, VM, or physical hardware required.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
bash "$PROJECT_ROOT/scripts/test-core.sh"
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) EXE_SUFFIX=.exe ;;
    *) EXE_SUFFIX= ;;
esac
TEST_BIN="$BUILD_DIR/ec_slot_guard_tests$EXE_SUFFIX"
"${CC:-gcc}" -std=c11 -O2 -Wall -Wextra -Werror \
    "$PROJECT_ROOT/tests/ec_slot_guard_tests.c" -o "$TEST_BIN"
"$TEST_BIN"
python3 -I "$PROJECT_ROOT/tests/test_runtime_matching.py"
