#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
dest="$BUILD_DIR/research/runtime-inventory"
root="$dest/iso"
mkdir -p "$root/boot/grub"
include="${GNU_EFI_INCLUDE:-/usr/include/efi}"
lib="${GNU_EFI_LIBDIR:-/usr/lib}"
gcc -I"$include" -I"$include/x86_64" -I"$include/protocol" \
    -fno-stack-protector -fpic -fshort-wchar -mno-red-zone -ffreestanding \
    -DEFI_FUNCTION_WRAPPER -O2 -Wall -Wextra -Werror \
    -c "$PROJECT_ROOT/src/RuntimeInventory.c" -o "$dest/RuntimeInventory.o"
ld -nostdlib -znocombreloc -T "$lib/elf_x86_64_efi.lds" -shared -Bsymbolic \
    "$lib/crt0-efi-x86_64.o" "$dest/RuntimeInventory.o" -L"$lib" -lefi -lgnuefi \
    -o "$dest/RuntimeInventory.so"
objcopy -j .text -j .sdata -j .data -j .rodata -j .dynamic -j .dynsym \
    -j .rel -j .rela -j .reloc --target=efi-app-x86_64 \
    "$dest/RuntimeInventory.so" "$root/RuntimeInventory.efi"
cp "$root/RuntimeInventory.efi" "$dest/"
cp "$BUILD_DIR/research/stage3/vmlinuz-stage3" "$BUILD_DIR/research/stage3/initramfs-stage3.cpio.gz" "$root/boot/"
cat > "$root/boot/grub/grub.cfg" <<'EOF'
set timeout=15
set default=0
terminal_output console
menuentry '1. SAVE firmware inventory to marked USB (no ACPI enable)' {
    set timeout=-1
    chainloader /RuntimeInventory.efi
    boot
}
menuentry '2. AFTER inventory: POST_SVAM diagnostic (expected freeze)' {
    linux /boot/vmlinuz-stage3 rdinit=/init k53diag_acpi_phase=post_svam efi=debug earlycon=efifb keep_bootcon ignore_loglevel loglevel=7 log_buf_len=8M console=ttyS0,115200 console=tty0 panic=0
    initrd /boot/initramfs-stage3.cpio.gz
}
EOF
cp "$PROJECT_ROOT/LICENSE" "$PROJECT_ROOT/THIRD_PARTY_NOTICES.md" "$root/"
cp -r "$PROJECT_ROOT/LICENSES" "$root/"
printf 'Select this writable volume for a K53SVAM inventory report.\r\n' > "$dest/K53PROBE.TAG"
grub-mkrescue -o "$dest/K53SJ-RUNTIME-INVENTORY.iso" "$root" > "$dest/package.log" 2>&1
(cd "$dest"; sha256sum RuntimeInventory.efi K53SJ-RUNTIME-INVENTORY.iso K53PROBE.TAG > SHA256SUMS)
printf 'Inventory artifacts: %s\n' "$dest"
