#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cache="${K53_KERNEL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/acpifirst-stage3}"
mkdir -p "$cache"
archive="$cache/linux-7.2.7.tar.xz"
if [ ! -f "$archive" ]; then
    curl -fL --retry 3 -o "$archive" https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-7.2.7.tar.xz
fi
(cd "$cache"; sha256sum -c "$repo/research/linux/kernel-source.sha256")
if [ ! -d "$cache/linux-7.2.7" ]; then
    tar -xf "$archive" -C "$cache"
fi
printf 'Verified source cache: %s\n' "$cache"
