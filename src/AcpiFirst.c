// SPDX-License-Identifier: MIT
#include <efi.h>
#include <efilib.h>
#include "acpi_core.h"

static UINT16 io_in16(UINT16 port)
{
    UINT16 value;
    __asm__ volatile ("inw %w1, %0" : "=a"(value) : "Nd"(port) : "memory");
    return value;
}
static VOID io_out8(UINT16 port, UINT8 value)
{
    __asm__ volatile ("outb %0, %w1" : : "a"(value), "Nd"(port) : "memory");
}

static VOID *find_config(EFI_GUID guid)
{
    UINTN i;
    for (i = 0; i < ST->NumberOfTableEntries; ++i)
        if (CompareGuid(&ST->ConfigurationTable[i].VendorGuid, &guid) == 0)
            return ST->ConfigurationTable[i].VendorTable;
    return NULL;
}

static BOOLEAN supported_machine(VOID)
{
    EFI_GUID guid = SMBIOS_TABLE_GUID;
    const UINT8 *entry = find_config(guid);
    UINTN length;
    if (!entry || !k53_equal(entry, "_SM_", 4)) return FALSE;
    length = entry[5];
    if (length < 31 || length > 64 || !k53_checksum(entry, length)) return FALSE;
    if (!k53_equal(entry + 16, "_DMI_", 5) ||
        !k53_checksum(entry + 16, 15)) return FALSE;
    if (k53_u16(entry + 22) == 0 || k53_u32(entry + 24) == 0) return FALSE;
    return k53_smbios_product((const UINT8 *)(UINTN)k53_u32(entry + 24),
                              k53_u16(entry + 22)) != 0;
}

static const UINT8 *find_fadt(VOID)
{
    EFI_GUID acpi2 = ACPI_20_TABLE_GUID, acpi1 = ACPI_TABLE_GUID;
    const UINT8 *rsdp = find_config(acpi2), *root;
    UINT64 address = 0;
    UINT32 length;
    UINTN stride = 4, offset;
    if (!rsdp) rsdp = find_config(acpi1);
    if (!rsdp || !k53_equal(rsdp, "RSD PTR ", 8) ||
        !k53_checksum(rsdp, 20)) return NULL;
    if (rsdp[15] >= 2) {
        length = k53_u32(rsdp + 20);
        if (length < 36 || length > 4096 || !k53_checksum(rsdp, length)) return NULL;
        address = k53_u64(rsdp + 24);
        if (address) stride = 8;
    }
    if (!address) address = k53_u32(rsdp + 16);
    if (!address) return NULL;
    root = (const UINT8 *)(UINTN)address;
    length = k53_u32(root + 4);
    if (!k53_equal(root, stride == 8 ? "XSDT" : "RSDT", 4) ||
        length < 36 || length > 1048576 || (length - 36) % stride ||
        !k53_checksum(root, length)) return NULL;
    for (offset = 36; offset < length; offset += stride) {
        const UINT8 *table;
        address = stride == 8 ? k53_u64(root + offset) : k53_u32(root + offset);
        if (!address) continue;
        table = (const UINT8 *)(UINTN)address;
        if (k53_equal(table, "FACP", 4)) return table;
    }
    return NULL;
}

/* Read-only discovery: select exactly one visible Windows installer volume. */
static EFI_STATUS find_installer(EFI_HANDLE *chosen)
{
    EFI_GUID fs_guid = SIMPLE_FILE_SYSTEM_PROTOCOL;
    EFI_HANDLE *handles = NULL;
    UINTN count = 0, matches = 0, i;
    EFI_STATUS status;
    *chosen = NULL;
    status = uefi_call_wrapper(BS->LocateHandleBuffer, 5, ByProtocol,
                              &fs_guid, NULL, &count, &handles);
    if (EFI_ERROR(status)) return status;
    for (i = 0; i < count; ++i) {
        EFI_FILE_IO_INTERFACE *fs;
        EFI_FILE_HANDLE root = NULL, wim = NULL, loader = NULL;
        CHAR16 *description;
        status = uefi_call_wrapper(BS->HandleProtocol, 3, handles[i], &fs_guid, (VOID **)&fs);
        if (EFI_ERROR(status)) continue;
        status = uefi_call_wrapper(fs->OpenVolume, 2, fs, &root);
        if (EFI_ERROR(status)) continue;
        CHAR16 *wim_path = L"\\sources\\boot.wim";
        status = uefi_call_wrapper(root->Open, 5, root, &wim,
                                  wim_path, EFI_FILE_MODE_READ, 0);
        if (EFI_ERROR(status)) {
            wim = NULL;
            wim_path = L"\\x64\\sources\\boot.wim";
            status = uefi_call_wrapper(root->Open, 5, root, &wim,
                                      wim_path, EFI_FILE_MODE_READ, 0);
        }
        if (!EFI_ERROR(status)) {
            status = uefi_call_wrapper(root->Open, 5, root, &loader,
                                      L"\\EFI\\BOOT\\BOOTX64.EFI", EFI_FILE_MODE_READ, 0);
            if (!EFI_ERROR(status)) {
                ++matches;
                *chosen = handles[i];
                description = DevicePathToStr(DevicePathFromHandle(handles[i]));
                Print(L"Windows installer candidate %d: %s\r\n", matches,
                      description ? description : L"(device path unavailable)");
                Print(L"Installer boot image: %s\r\n", wim_path);
                if (description) FreePool(description);
            }
        }
        if (loader) uefi_call_wrapper(loader->Close, 1, loader);
        if (wim) uefi_call_wrapper(wim->Close, 1, wim);
        uefi_call_wrapper(root->Close, 1, root);
    }
    FreePool(handles);
    if (matches == 1) return EFI_SUCCESS;
    *chosen = NULL;
    if (matches == 0) {
        Print(L"STOP: no visible Windows installer filesystem.\r\n");
        Print(L"Need sources/boot.wim OR x64/sources/boot.wim, plus EFI/BOOT/BOOTX64.EFI.\r\n");
        Print(L"An ISO file stored on Ventoy is not an extracted installer filesystem.\r\n");
        return EFI_NOT_FOUND;
    }
    Print(L"STOP: more than one Windows installer found; leave only one connected.\r\n");
    return EFI_INVALID_PARAMETER;
}

EFI_STATUS efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *system)
{
#ifdef K53_DISCOVERY_TEST
    EFI_HANDLE test_target;
    EFI_STATUS test_status;
    InitializeLib(image, system);
    Print(L"K53_DISCOVERY_TEST: read-only discovery; no SMI writes or chainload.\r\n");
    test_status = find_installer(&test_target);
    Print(L"K53_DISCOVERY_TEST result=%r\r\n", test_status);
    return test_status;
#else
    EFI_GUID loaded_guid = LOADED_IMAGE_PROTOCOL;
    EFI_LOADED_IMAGE *loaded;
    EFI_DEVICE_PATH *path;
    EFI_HANDLE child;
    EFI_HANDLE target_device;
    EFI_STATUS status;
    struct k53_acpi_ports ports;
    const UINT8 *fadt;
    CHAR16 *self_path;
    CHAR16 *target = L"\\EFI\\BOOT\\BOOTX64.EFI";
    UINTN n, i;
    UINT16 control;
    int validation;

    InitializeLib(image, system);
    Print(L"\r\nAcpiFirst / K53SJ direct boot experiment v3 (dual-arch media)\r\n");
    Print(L"No BIOS flash, no file writes, no boot-order changes.\r\n");
    if (!supported_machine()) {
        Print(L"REFUSED: SMBIOS product is not the supported K53SJ.\r\n");
        return EFI_UNSUPPORTED;
    }
    fadt = find_fadt();
    if (!fadt) {
        Print(L"REFUSED: no valid ACPI root/FADT found.\r\n");
        return EFI_NOT_FOUND;
    }
    validation = k53_parse_fadt(fadt, k53_u32(fadt + 4), &ports);
    if (validation) {
        Print(L"REFUSED: FADT layout differs from captured K53SJ (check %d).\r\n", validation);
        return EFI_UNSUPPORTED;
    }
    status = uefi_call_wrapper(BS->HandleProtocol, 3, image, &loaded_guid, (VOID **)&loaded);
    if (EFI_ERROR(status)) return status;
    self_path = DevicePathToStr(loaded->FilePath);
    if (!self_path) return EFI_OUT_OF_RESOURCES;
    n = StrLen(self_path);
    if (n >= 11 && StriCmp(self_path + n - 11, L"BOOTX64.EFI") == 0) {
        Print(L"REFUSED: keep this program named AcpiFirst.efi; do not replace BOOTX64.EFI.\r\n");
        FreePool(self_path);
        return EFI_INVALID_PARAMETER;
    }
    FreePool(self_path);
    Print(L"Scanning visible filesystems for a Windows installer...\r\n");
    status = find_installer(&target_device);
    if (EFI_ERROR(status)) return status;
    path = FileDevicePath(target_device, target);
    if (!path) return EFI_OUT_OF_RESOURCES;
    Print(L"Loading original %s on the selected installer filesystem...\r\n", target);
    status = uefi_call_wrapper(BS->LoadImage, 6, FALSE, image, path, NULL, 0, &child);
    FreePool(path);
    if (EFI_ERROR(status)) {
        Print(L"LoadImage failed: %r. Check the original installer bootloader.\r\n", status);
        return status;
    }
    control = io_in16(ports.pm1a);
    Print(L"PM1_CNT=%04x SCI_EN=%d; SMI_CMD=%04x ACPI_ENABLE=%02x\r\n",
          control, control & 1, ports.smi, ports.enable);
    if (!(control & 1)) {
        Print(L"SMI outb ENTER: port=00B2 value=A0\r\n");
        io_out8(ports.smi, ports.enable);
        Print(L"SMI outb RETURN\r\n");
        for (i = 0; i < 3000; ++i) {
            control = io_in16(ports.pm1a);
            if (control & 1) break;
            uefi_call_wrapper(BS->Stall, 1, 1000);
        }
        if (!(control & 1)) {
            Print(L"STOP: SCI_EN stayed zero for 3 seconds; not starting Windows.\r\n");
            uefi_call_wrapper(BS->UnloadImage, 1, child);
            return EFI_TIMEOUT;
        }
    }
    Print(L"ACPI enabled (SCI_EN=1). Starting original Windows loader.\r\n");
    uefi_call_wrapper(BS->Stall, 1, 1500000);
    status = uefi_call_wrapper(BS->StartImage, 3, child, NULL, NULL);
    Print(L"Windows loader returned: %r\r\n", status);
    uefi_call_wrapper(BS->UnloadImage, 1, child);
    return status;
#endif
}
