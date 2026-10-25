#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
efi_include="${GNU_EFI_INCLUDE:-/usr/include/efi}"
efi_lib="${GNU_EFI_LIBDIR:-/usr/lib}"
iso_root="$BUILD_DIR/iso"
dist="$BUILD_DIR/dist"
mkdir -p "$iso_root/boot/grub" "$dist" "$BUILD_DIR/test-only"
bash "$PROJECT_ROOT/scripts/test-core.sh"

compile_efi() {
    local name=$1
    shift
    "${CC:-gcc}" -I"$efi_include" -I"$efi_include/x86_64" -I"$efi_include/protocol" \
        -fno-stack-protector -fpic -fshort-wchar -mno-red-zone -ffreestanding \
        -DEFI_FUNCTION_WRAPPER -O2 -Wall -Wextra -Werror "$@" \
        -c "$PROJECT_ROOT/src/AcpiFirst.c" -o "$BUILD_DIR/$name.o"
    "${LD:-ld}" -nostdlib -znocombreloc -T "$efi_lib/elf_x86_64_efi.lds" -shared -Bsymbolic \
        "$efi_lib/crt0-efi-x86_64.o" "$BUILD_DIR/$name.o" \
        -L"$efi_lib" -lefi -lgnuefi -o "$BUILD_DIR/$name.so"
    "${OBJCOPY:-objcopy}" -j .text -j .sdata -j .data -j .rodata -j .dynamic -j .dynsym \
        -j .rel -j .rela -j .reloc --target=efi-app-x86_64 \
        "$BUILD_DIR/$name.so" "$BUILD_DIR/$name.efi"
}
compile_efi AcpiFirst
compile_efi DiscoveryTest -DK53_DISCOVERY_TEST -Wno-unused-function
cp "$BUILD_DIR/AcpiFirst.efi" "$dist/AcpiFirst.efi"
cp "$BUILD_DIR/AcpiFirst.efi" "$iso_root/AcpiFirst.efi"
cp "$BUILD_DIR/DiscoveryTest.efi" "$BUILD_DIR/test-only/DiscoveryTest.efi"
cp "$PROJECT_ROOT/boot/grub.cfg" "$iso_root/boot/grub/grub.cfg"
mkdir -p "$dist/LICENSES" "$iso_root/LICENSES"
cp "$PROJECT_ROOT/LICENSE" "$PROJECT_ROOT/THIRD_PARTY_NOTICES.md" "$PROJECT_ROOT/README.md" "$dist/"
cp "$PROJECT_ROOT/LICENSE" "$PROJECT_ROOT/THIRD_PARTY_NOTICES.md" "$iso_root/"
cp "$PROJECT_ROOT"/LICENSES/*.txt "$dist/LICENSES/"
cp "$PROJECT_ROOT"/LICENSES/*.txt "$iso_root/LICENSES/"
{
    printf 'AcpiFirst direct-ISO v3 build\nUTC: '
    date -u '+%Y-%m-%dT%H:%M:%SZ'
    "${CC:-gcc}" --version | head -n 1
    "${LD:-ld}" --version | head -n 1
    grub-mkrescue --version
    if command -v dpkg-query >/dev/null 2>&1; then
        dpkg-query -W gnu-efi grub-common grub-efi-amd64-bin grub-pc-bin xorriso mtools
    fi
} > "$dist/BUILD-MANIFEST.txt"
cp "$dist/BUILD-MANIFEST.txt" "$iso_root/"
grub-mkrescue -o "$dist/AcpiFirst-Direct-v3-UEFI.iso" "$iso_root" > "$BUILD_DIR/package.log" 2>&1
(cd "$dist"; sha256sum AcpiFirst.efi AcpiFirst-Direct-v3-UEFI.iso > SHA256SUMS)
printf 'Artifacts: %s\n' "$dist"
