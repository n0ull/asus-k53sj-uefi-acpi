#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cache="${K53_KERNEL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/acpifirst-stage3}"
source_dir="$cache/linux-7.2.7"
out="$cache/build"
dest="$repo/build/research/ec-watch"
mkdir -p "$dest/iso/boot/grub"
if [ -f "$cache/.ec-slot-applied" ]; then
    echo 'Cache contains slot38 intervention; use a fresh cache for pristine EC WATCH.' >&2
    exit 1
fi
if [ ! -f "$cache/.stage3-applied" ]; then
    bash "$repo/research/linux/build-stage-probe.sh"
fi
stamp=$(sha256sum "$repo/research/linux/apply_ec_watch.py" | cut -d' ' -f1)
if [ -f "$cache/.ec-watch-applied" ]; then
    [ "$(cat "$cache/.ec-watch-applied")" = "$stamp" ] || {
        echo 'EC watch source changed; use a fresh cache or restore the stage3 source first.' >&2; exit 1;
    }
else
    python3 "$repo/research/linux/apply_ec_watch.py" "$source_dir"
    printf '%s\n' "$stamp" > "$cache/.ec-watch-applied"
fi
# Keep the stage3 configuration/version; this is an opt-in instrumentation variant.
make -C "$source_dir" O="$out" -j"${JOBS:-10}" bzImage > "$dest/build.log" 2>&1
cp "$out/arch/x86/boot/bzImage" "$dest/iso/boot/vmlinuz-ec-watch"
cp "$repo/build/research/stage3/initramfs-stage3.cpio.gz" "$dest/iso/boot/"
cat > "$dest/iso/boot/grub/grub.cfg" <<'EOF'
set timeout=15
set default=0
terminal_output console
menuentry '1. EC WATCH: read pointers BEFORE/AFTER SVAM, then enable ACPI' {
    linux /boot/vmlinuz-ec-watch rdinit=/init k53diag_ec_watch k53diag_acpi_phase=post_svam efi=debug earlycon=efifb keep_bootcon ignore_loglevel loglevel=7 log_buf_len=8M console=ttyS0,115200 console=tty0 panic=0
    initrd /boot/initramfs-stage3.cpio.gz
}
menuentry '2. EC WATCH control: enable ACPI BEFORE SVAM; export logs' {
    linux /boot/vmlinuz-ec-watch rdinit=/init k53diag_ec_watch k53diag_acpi_phase=pre_svam efi=debug earlycon=efifb keep_bootcon ignore_loglevel loglevel=7 log_buf_len=8M console=ttyS0,115200 console=tty0 panic=0
    initrd /boot/initramfs-stage3.cpio.gz
}
EOF
cp "$cache/linux-7.2.7-ec-watch-extra.patch" "$dest/"
cp "$repo/LICENSE" "$repo/THIRD_PARTY_NOTICES.md" "$dest/iso/"
cp -r "$repo/LICENSES" "$dest/iso/"
grub-mkrescue -o "$dest/K53SJ-EC-WATCH.iso" "$dest/iso" > "$dest/package.log" 2>&1
cp "$dest/iso/boot/vmlinuz-ec-watch" "$dest/"
(cd "$dest"; sha256sum K53SJ-EC-WATCH.iso vmlinuz-ec-watch > SHA256SUMS)
printf 'EC watch ISO: %s/K53SJ-EC-WATCH.iso\n' "$dest"
