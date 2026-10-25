#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Shared paths. All generated files stay in BUILD_DIR.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/build}"
mkdir -p "$BUILD_DIR"
BUILD_DIR="$(cd -- "$BUILD_DIR" && pwd)"
export PROJECT_ROOT BUILD_DIR
