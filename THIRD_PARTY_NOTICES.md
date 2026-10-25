# License scope and upstream components

The root MIT license covers this project's original EFI application, parsing
helpers, test/build scripts, boot configuration and original documentation.

## GNU-EFI

The application links against the system-provided GNU-EFI libraries and startup
object. The tested package is Ubuntu `gnu-efi 3.0.15-1build1`. Its components carry
their own BSD-style and other notices; the package's complete copyright summary
is retained in `LICENSES/GNU-EFI-COPYRIGHT.txt`. No GNU-EFI library source is
vendored or relicensed by this repository.

Upstream: https://sourceforge.net/projects/gnu-efi/

## GNU GRUB

The generated ISO includes the system's GRUB bootloader, produced by
`grub-mkrescue`. GRUB is not covered by this project's MIT license. The tested
Ubuntu package's copyright summary and GPL version 3 text are retained in
`LICENSES/GRUB-COPYRIGHT.txt` and `LICENSES/GPL-3.0.txt`. Preserve these notices
and the applicable corresponding-source requirements when distributing a
generated ISO. The build records the package version in its build manifest.

Upstream: https://www.gnu.org/software/grub/

## Linux diagnostic research

`research/linux/patches/` contains a diagnostic patch against upstream Linux
7.2.7, including context from GPL-2.0-only kernel files. The patch is not
relicensed under MIT. The original kernel's license and per-file notices apply;
the GPL version 2 text is included in `LICENSES/GPL-2.0.txt`.

The configurations were generated from an Arch Linux configuration and the
diagnostic build. They retain their generated headers. Original BusyBox-init
and boot-menu scripts in this repository are project code; BusyBox itself and
the diagnostic Linux binaries are not included in the Git source set.

Upstream: https://www.kernel.org/

## Firmware and Windows

ASUS BIOS images, captured ACPI tables, Windows bootloaders, Windows installation
images and private machine logs are not included in the Git source set. Use
original installation media supplied separately. The software starts the
existing Windows EFI loader; it does not distribute or patch that loader.
