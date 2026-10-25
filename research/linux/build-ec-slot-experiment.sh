#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cache="${K53_KERNEL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/acpifirst-stage3}"
source_dir="$cache/linux-7.2.7"
out="$cache/build"
dest="$repo/build/research/ec-slot38"
mkdir -p "$dest/iso/boot/grub"
gcc -std=c11 -Wall -Wextra -Werror "$repo/tests/ec_slot_guard_tests.c" -o "$dest/guard-tests"
"$dest/guard-tests"
if [ ! -f "$cache/.ec-watch-applied" ]; then
    bash "$repo/research/linux/build-ec-watch.sh"
fi
stamp=$(cat "$repo/research/linux/apply_ec_slot_experiment.py" "$repo/research/linux/ec_slot_guard.h" | sha256sum | cut -d' ' -f1)
if [ -f "$cache/.ec-slot-applied" ]; then
    [ "$(cat "$cache/.ec-slot-applied")" = "$stamp" ] || {
        echo 'Slot38 source changed; select a fresh cache.' >&2; exit 1;
    }
else
    python3 "$repo/research/linux/apply_ec_slot_experiment.py" "$source_dir"
    printf '%s\n' "$stamp" > "$cache/.ec-slot-applied"
fi
make -C "$source_dir" O="$out" -j"${JOBS:-10}" bzImage > "$dest/build.log" 2>&1
cp "$out/arch/x86/boot/bzImage" "$dest/iso/boot/vmlinuz-slot38"
cp "$repo/build/research/stage3/initramfs-stage3.cpio.gz" "$dest/iso/boot/"
cat > "$dest/iso/boot/grub/grub.cfg" <<'EOF'
set timeout=-1
set default=0
terminal_output console
menuentry '1. BASELINE: read-only EC WATCH, enable ACPI after SVAM' {
    linux /boot/vmlinuz-slot38 rdinit=/init k53diag_ec_watch k53diag_acpi_phase=post_svam efi=debug earlycon=efifb keep_bootcon ignore_loglevel loglevel=7 log_buf_len=8M console=ttyS0,115200 console=tty0 panic=0
    initrd /boot/initramfs-stage3.cpio.gz
}
menuentry '2. RAM-ONLY TEST: temporary PHYSICAL EC slot38, then CLEANUP' {
    linux /boot/vmlinuz-slot38 rdinit=/init k53diag_ec_watch k53diag_ec_restore38 k53diag_acpi_phase=post_svam efi=debug earlycon=efifb keep_bootcon ignore_loglevel loglevel=7 log_buf_len=8M console=ttyS0,115200 console=tty0 panic=0
    initrd /boot/initramfs-stage3.cpio.gz
}
EOF
cp "$cache/linux-7.2.7-slot38-extra.patch" "$dest/"
cp "$repo/research/linux/ec_slot_guard.h" "$dest/"
cp "$repo/LICENSE" "$repo/THIRD_PARTY_NOTICES.md" "$dest/iso/"
cp -r "$repo/LICENSES" "$dest/iso/"
grub-mkrescue -o "$dest/K53SJ-EC-SLOT38-EXPERIMENT.iso" "$dest/iso" > "$dest/package.log" 2>&1
(cd "$dest"; sha256sum K53SJ-EC-SLOT38-EXPERIMENT.iso iso/boot/vmlinuz-slot38 > SHA256SUMS)
printf 'RAM-only experiment: %s/K53SJ-EC-SLOT38-EXPERIMENT.iso\n' "$dest"
