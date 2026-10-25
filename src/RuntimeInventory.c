// SPDX-License-Identifier: MIT
/* Diagnostic inventory only: never invoke SMI, SVAM, or variable services. */
#include <efi.h>
#include <efilib.h>
#include <stdarg.h>

typedef struct link { struct link *next, *prev; } LINK;
typedef struct { VOID *base; UINT64 size; VOID *fixups; EFI_HANDLE handle; LINK link; } IMAGE;
typedef struct { UINT32 type; UINTN tpl; VOID *notify, *context; EFI_EVENT *event; LINK link; } EVENT;
typedef struct { LINK images, events; } ARCH;
static CHAR8 report[262144];
static UINTN used;
static EFI_MEMORY_DESCRIPTOR *map;
static UINTN map_size, descriptor_size;
static IMAGE images[128];
static UINTN image_count;

static VOID line(CHAR16 *format, ...)
{
    CHAR16 temp[512];
    va_list args;
    UINTN i;
    va_start(args, format);
    VSPrint(temp, sizeof(temp), format, args);
    va_end(args);
    for (i = 0; temp[i] && used + 1 < sizeof(report); ++i)
        report[used++] = temp[i] < 128 ? (CHAR8)temp[i] : '?';
    report[used] = 0;
}

static BOOLEAN readable(const VOID *pointer, UINTN bytes)
{
    UINT64 start = (UINTN)pointer, end;
    UINTN offset;
    if (!start || !bytes || bytes > (~(UINT64)0) - start) return FALSE;
    end = start + bytes;
    for (offset = 0; offset + sizeof(*map) <= map_size; offset += descriptor_size) {
        EFI_MEMORY_DESCRIPTOR *d = (VOID *)((UINT8 *)map + offset);
        UINT64 length;
        if (d->Type == EfiReservedMemoryType || d->Type == EfiUnusableMemory ||
            d->Type == EfiMemoryMappedIO || d->Type == EfiMemoryMappedIOPortSpace ||
            d->Type == EfiPalCode || d->NumberOfPages > (~(UINT64)0) / 4096) continue;
        length = d->NumberOfPages * 4096;
        if (start >= d->PhysicalStart && end >= d->PhysicalStart &&
            end - d->PhysicalStart <= length) return TRUE;
    }
    return FALSE;
}

static VOID owner(CHAR16 *name, VOID *address)
{
    UINTN i, value = (UINTN)address;
    for (i = 0; i < image_count; ++i) {
        UINTN base = (UINTN)images[i].base;
        if (value >= base && value - base < images[i].size) {
            line(L"%s=%lx image=%d rva=%lx\r\n", name, value, i, value - base);
            return;
        }
    }
    line(L"%s=%lx image=UNKNOWN\r\n", name, value);
}

static VOID bytes(CHAR16 *name, VOID *pointer, UINTN count)
{
    UINTN i;
    line(L"%s:", name);
    if (!readable(pointer, count)) { line(L" UNREADABLE\r\n"); return; }
    for (i = 0; i < count; ++i) line(L" %02x", ((UINT8 *)pointer)[i]);
    line(L"\r\n");
}

static VOID inventory(VOID)
{
    EFI_GUID arch_guid = {0xb7dfb4e1,0x052f,0x449f,{0x87,0xbe,0x98,0x18,0xfc,0x91,0xb7,0x33}};
    EFI_GUID shared_guid = {0x34cf7ec3,0x50f4,0x4544,{0x8f,0x50,0xfb,0x1f,0x9f,0xf6,0x07,0x48}};
    ARCH *arch = NULL;
    VOID *shared = NULL;
    LINK *node, *head;
    EFI_STATUS status;
    UINTN count, i;
    line(L"K53SVAM INVENTORY v1 BEFORE ExitBootServices\r\n");
    line(L"UEFI revision=%08x vendor=%s RT=%lx BS=%lx\r\n",
         ST->Hdr.Revision, ST->FirmwareVendor, (UINTN)RT, (UINTN)BS);
    status = uefi_call_wrapper(BS->LocateProtocol, 3, &arch_guid, NULL, (VOID **)&arch);
    line(L"RuntimeArch status=%r ptr=%lx\r\n", status, (UINTN)arch);
    if (!EFI_ERROR(status) && readable(arch, sizeof(*arch))) {
        head = &arch->images;
        node = head->next;
        for (count = 0; node != head && count < 128; ++count) {
            IMAGE *entry;
            UINT8 *base;
            UINT32 pe;
            if ((UINTN)node < EFI_FIELD_OFFSET(IMAGE, link)) break;
            entry = (VOID *)((UINT8 *)node - EFI_FIELD_OFFSET(IMAGE, link));
            if (!readable(entry, sizeof(*entry))) { line(L"INVALID image node\r\n"); break; }
            images[image_count++] = *entry;
            line(L"IMAGE %d base=%lx size=%lx fixups=%lx handle=%lx\r\n", count,
                 (UINTN)entry->base, entry->size, (UINTN)entry->fixups, (UINTN)entry->handle);
            base = entry->base;
            if (readable(base, 64) && base[0] == 'M' && base[1] == 'Z') {
                CopyMem(&pe, base + 60, 4);
                if (pe < entry->size && entry->size - pe >= 64 && readable(base + pe, 64)) {
                    UINT32 ep;
                    CopyMem(&ep, base + pe + 40, 4);
                    line(L"PE entry_rva=%lx\r\n", (UINTN)ep);
                    if (ep < entry->size && entry->size - ep >= 64)
                        bytes(L"ENTRY64", base + ep, 64);
                }
            }
            node = node->next;
        }
        if (node != head) line(L"IMAGE list incomplete/capped\r\n");
        head = &arch->events;
        node = head->next;
        for (count = 0; node != head && count < 128; ++count) {
            EVENT *entry;
            if ((UINTN)node < EFI_FIELD_OFFSET(EVENT, link)) break;
            entry = (VOID *)((UINT8 *)node - EFI_FIELD_OFFSET(EVENT, link));
            if (!readable(entry, sizeof(*entry))) { line(L"INVALID event node\r\n"); break; }
            line(L"EVENT %d type=%08x tpl=%lx context=%lx event_ptr=%lx\r\n",
                 count, entry->type, entry->tpl, (UINTN)entry->context, (UINTN)entry->event);
            owner(L"NOTIFY", entry->notify);
            node = node->next;
        }
        if (node != head) line(L"EVENT list incomplete/capped\r\n");
    }
    owner(L"SVAM", (VOID *)RT->SetVirtualAddressMap);
    owner(L"CONVERT", (VOID *)RT->ConvertPointer);
    owner(L"SETVARIABLE", (VOID *)RT->SetVariable);
    status = uefi_call_wrapper(BS->LocateProtocol, 3, &shared_guid, NULL, &shared);
    line(L"ACPI_SHARED status=%r ptr=%lx\r\n", status, (UINTN)shared);
    if (!EFI_ERROR(status) && readable(shared, 72)) {
        for (i = 0; i < 9; ++i) {
            VOID *value;
            CopyMem(&value, (UINT8 *)shared + i * 8, 8);
            line(L"SHARED offset=%lx ", i * 8);
            owner(L"VALUE", value);
        }
    }
    line(L"END inventory; no SVAM/SMI/SetVariable invoked by this application\r\n");
}

static EFI_STATUS save(VOID)
{
    EFI_GUID fs_guid = SIMPLE_FILE_SYSTEM_PROTOCOL;
    EFI_HANDLE *handles = NULL;
    EFI_FILE_HANDLE selected = NULL;
    UINTN count = 0, i, matches = 0;
    EFI_STATUS status = uefi_call_wrapper(BS->LocateHandleBuffer, 5, ByProtocol,
                                           &fs_guid, NULL, &count, &handles);
    if (EFI_ERROR(status)) return status;
    for (i = 0; i < count; ++i) {
        EFI_FILE_IO_INTERFACE *fs;
        EFI_FILE_HANDLE root = NULL, tag = NULL;
        status = uefi_call_wrapper(BS->HandleProtocol, 3, handles[i], &fs_guid, (VOID **)&fs);
        if (EFI_ERROR(status)) continue;
        status = uefi_call_wrapper(fs->OpenVolume, 2, fs, &root);
        if (EFI_ERROR(status)) continue;
        status = uefi_call_wrapper(root->Open, 5, root, &tag, L"\\K53PROBE.TAG", EFI_FILE_MODE_READ, 0);
        if (!EFI_ERROR(status)) {
            uefi_call_wrapper(tag->Close, 1, tag);
            ++matches;
            if (!selected) { selected = root; root = NULL; }
        }
        if (root) uefi_call_wrapper(root->Close, 1, root);
    }
    FreePool(handles);
    if (matches != 1) {
        if (selected) uefi_call_wrapper(selected->Close, 1, selected);
        Print(L"STOP: need exactly ONE readable volume containing K53PROBE.TAG; found %d\r\n", matches);
        return EFI_NOT_FOUND;
    }
    for (i = 0; i < 100; ++i) {
        CHAR16 name[32];
        EFI_FILE_HANDLE file = NULL;
        UINTN length = used;
        SPrint(name, sizeof(name), L"\\K53SVAM-%02d.TXT", i);
        status = uefi_call_wrapper(selected->Open, 5, selected, &file, name, EFI_FILE_MODE_READ, 0);
        if (!EFI_ERROR(status)) { uefi_call_wrapper(file->Close, 1, file); continue; }
        if (status != EFI_NOT_FOUND) break;
        status = uefi_call_wrapper(selected->Open, 5, selected, &file, name,
                                   EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE, 0);
        if (EFI_ERROR(status)) break;
        status = uefi_call_wrapper(file->Write, 3, file, &length, report);
        if (!EFI_ERROR(status) && length != used) status = EFI_DEVICE_ERROR;
        if (!EFI_ERROR(status)) status = uefi_call_wrapper(file->Flush, 1, file);
        uefi_call_wrapper(file->Close, 1, file);
        Print(L"Inventory save %s: %r (%d bytes)\r\n", name, status, length);
        uefi_call_wrapper(selected->Close, 1, selected);
        return status;
    }
    uefi_call_wrapper(selected->Close, 1, selected);
    return EFI_ERROR(status) ? status : EFI_OUT_OF_RESOURCES;
}

EFI_STATUS efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *system)
{
    EFI_STATUS status;
    UINTN key, capacity;
    UINT32 version;
    InitializeLib(image, system);
    Print(L"K53SVAM read-only firmware inventory; writes one report to marked USB.\r\n");
    map_size = 0;
    status = uefi_call_wrapper(BS->GetMemoryMap, 5, &map_size, NULL, &key, &descriptor_size, &version);
    if (status != EFI_BUFFER_TOO_SMALL || descriptor_size < sizeof(*map)) return EFI_DEVICE_ERROR;
    capacity = map_size + 64 * descriptor_size;
    status = uefi_call_wrapper(BS->AllocatePool, 3, EfiLoaderData, capacity, (VOID **)&map);
    if (EFI_ERROR(status)) return status;
    map_size = capacity;
    status = uefi_call_wrapper(BS->GetMemoryMap, 5, &map_size, map, &key, &descriptor_size, &version);
    if (!EFI_ERROR(status) && descriptor_size >= sizeof(*map)) {
        inventory();
        status = save();
    }
    FreePool(map);
    Print(L"K53SVAM inventory finished: %r\r\n", status);
    return status;
}
