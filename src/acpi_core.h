// SPDX-License-Identifier: MIT
#ifndef K53_ACPI_CORE_H
#define K53_ACPI_CORE_H
#include <stddef.h>
#include <stdint.h>

static uint16_t k53_u16(const uint8_t *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}
static uint32_t k53_u32(const uint8_t *p)
{
    return (uint32_t)k53_u16(p) | ((uint32_t)k53_u16(p + 2) << 16);
}
static uint64_t k53_u64(const uint8_t *p)
{
    return (uint64_t)k53_u32(p) | ((uint64_t)k53_u32(p + 4) << 32);
}
static int k53_equal(const uint8_t *a, const char *b, size_t n)
{
    size_t i;
    for (i = 0; i < n; ++i)
        if (a[i] != (uint8_t)b[i]) return 0;
    return 1;
}
static int k53_checksum(const uint8_t *p, size_t n)
{
    uint8_t sum = 0;
    size_t i;
    for (i = 0; i < n; ++i) sum = (uint8_t)(sum + p[i]);
    return sum == 0;
}

struct k53_acpi_ports {
    uint16_t smi;
    uint8_t enable;
    uint16_t pm1a;
};

/* Restrict hardware writes to the layout captured from this K53SJ. */
static int k53_parse_fadt(const uint8_t *p, size_t available,
                          struct k53_acpi_ports *ports)
{
    uint32_t length;
    if (available < 116 || !k53_equal(p, "FACP", 4)) return 1;
    length = k53_u32(p + 4);
    if (length < 116 || length > available || length > 65536) return 2;
    if (!k53_checksum(p, length)) return 3;
    if (!k53_equal(p + 10, "_ASUS_", 6)) return 4;
    if (k53_u32(p + 112) & (1U << 20)) return 5; /* HW_REDUCED_ACPI */
    if (k53_u32(p + 48) != 0xb2 || p[52] != 0xa0) return 6;
    if (k53_u32(p + 64) != 0x404 || k53_u32(p + 68) != 0 || p[89] != 2) return 7;
    if (length >= 184 && k53_u64(p + 176) != 0) {
        if (p[172] != 1 || p[173] < 16 || p[174] != 0 ||
            k53_u64(p + 176) != 0x404) return 8;
    }
    ports->smi = 0xb2;
    ports->enable = 0xa0;
    ports->pm1a = 0x404;
    return 0;
}

/* SMBIOS type 1 product or type 2 board product, bounded string traversal. */
static int k53_smbios_product(const uint8_t *p, size_t length)
{
    size_t offset = 0;
    while (offset + 4 <= length) {
        size_t formatted = p[offset + 1], strings, end, pos;
        unsigned index, current;
        uint8_t type = p[offset];
        if (formatted < 4 || formatted > length - offset) return 0;
        strings = offset + formatted;
        end = strings;
        while (end + 1 < length && (p[end] != 0 || p[end + 1] != 0)) ++end;
        if (end + 1 >= length) return 0;
        if ((type == 1 || type == 2) && formatted >= 6) {
            index = p[offset + 5];
            pos = strings;
            for (current = 1; index && current <= index && pos <= end; ++current) {
                size_t start = pos;
                while (pos <= end && p[pos]) ++pos;
                if (current == index && pos - start == 5 &&
                    k53_equal(p + start, "K53SJ", 5)) return 1;
                ++pos;
            }
        }
        if (type == 127) return 0;
        offset = end + 2;
    }
    return 0;
}
#endif
