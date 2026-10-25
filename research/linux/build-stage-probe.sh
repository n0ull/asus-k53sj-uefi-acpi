#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cache="${K53_KERNEL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/acpifirst-stage3}"
source_dir="$cache/linux-7.2.7"
kernel_out="$cache/build"
dest="$repo/build/research/stage3"
mkdir -p "$dest"
if [ -f "$cache/.ec-watch-applied" ]; then
    echo 'Cache contains stage4 probes; use a fresh K53_KERNEL_CACHE for pristine stage3.' >&2
    exit 1
fi
bash "$repo/research/linux/prepare-stage-source.sh"
stamp=$(cat "$repo/research/linux/patches/linux-7.2.7-k53sj-diag2.patch" \
            "$repo/research/linux/apply_phase_probe.py" | sha256sum | cut -d' ' -f1)
if [ -f "$cache/.stage3-applied" ]; then
    [ "$(cat "$cache/.stage3-applied")" = "$stamp" ] || {
        echo 'Source patch changed; select a fresh K53_KERNEL_CACHE.' >&2; exit 1;
    }
else
    (cd "$source_dir"; patch -p1 < "$repo/research/linux/patches/linux-7.2.7-k53sj-diag2.patch")
    python3 "$repo/research/linux/apply_phase_probe.py" "$source_dir"
    printf '%s\n' "$stamp" > "$cache/.stage3-applied"
fi
mkdir -p "$kernel_out"
cp "$repo/research/linux/configs/diagnostic.config" "$kernel_out/.config"
cd "$source_dir"
scripts/config --file "$kernel_out/.config" --set-str LOCALVERSION '-k53sj-stage3'
make O="$kernel_out" olddefconfig > "$dest/configure.log" 2>&1
printf 'Building stage3 kernel; log: %s/build.log\n' "$dest"
make O="$kernel_out" -j"${JOBS:-10}" bzImage > "$dest/build.log" 2>&1

root="$cache/initramfs"
iso="$cache/iso"
mkdir -p "$root"/{bin,sbin,etc,proc,sys,dev,tmp,run,mnt/usb,usr/bin,usr/sbin} "$iso/boot/grub"
cp --remove-destination /usr/bin/busybox "$root/bin/busybox"
for applet in $(/usr/bin/busybox --list); do
    [ "$applet" = busybox ] && continue
    ln -sf busybox "$root/bin/$applet"
done
cp "$repo/research/linux/initramfs/init" "$root/init"
chmod +x "$root/init"
cat > "$root/bin/diag-save" <<'EOF'
#!/bin/sh
set -eu
target=${1:?Usage: diag-save /mounted/usb}
mountpoint -q "$target" || { echo 'Target is not mounted'; exit 1; }
dmesg > /tmp/k53diag/dmesg.txt
tar -czf /tmp/k53diag.tar.gz -C /tmp k53diag
cp /tmp/k53diag.tar.gz "$target/"
sync
echo "Saved $target/k53diag.tar.gz"
EOF
chmod +x "$root/bin/diag-save"
python3 - "$root" "$cache/initramfs.list" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
lines = []
for p in sorted(root.rglob('*')):
    name = '/' + str(p.relative_to(root))
    if p.is_symlink():
        lines.append(f'slink {name} {p.readlink()} 777 0 0')
    elif p.is_dir():
        lines.append(f'dir {name} 755 0 0')
    elif p.is_file():
        mode = '755' if p.stat().st_mode & 0o111 else '644'
        lines.append(f'file {name} {p} {mode} 0 0')
lines += ['nod /dev/console 600 0 0 c 5 1', 'nod /dev/null 666 0 0 c 1 3',
          'nod /dev/tty 666 0 0 c 5 0']
Path(sys.argv[2]).write_text('\n'.join(lines) + '\n')
PY
"$kernel_out/usr/gen_init_cpio" "$cache/initramfs.list" | gzip -9 > "$iso/boot/initramfs-stage3.cpio.gz"
cp "$kernel_out/arch/x86/boot/bzImage" "$iso/boot/vmlinuz-stage3"
cp "$repo/research/linux/stage-probe-grub.cfg" "$iso/boot/grub/grub.cfg"
grub-mkrescue -o "$dest/K53SJ-EFI-STAGE3.iso" "$iso" > "$dest/package.log" 2>&1
cp "$iso/boot/vmlinuz-stage3" "$iso/boot/initramfs-stage3.cpio.gz" "$dest/"
cp "$cache/linux-7.2.7-stage3-extra.patch" "$kernel_out/.config" "$dest/"
(cd "$dest"; sha256sum K53SJ-EFI-STAGE3.iso vmlinuz-stage3 initramfs-stage3.cpio.gz > SHA256SUMS)
printf 'Stage3 image ready: %s/K53SJ-EFI-STAGE3.iso\n' "$dest"
