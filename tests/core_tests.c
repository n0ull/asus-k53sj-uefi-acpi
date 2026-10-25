// SPDX-License-Identifier: MIT
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "acpi_core.h"

static void fix_checksum(uint8_t *p, size_t n)
{
    size_t i;
    uint8_t sum = 0;
    p[9] = 0;
    for (i = 0; i < n; ++i) sum = (uint8_t)(sum + p[i]);
    p[9] = (uint8_t)(0 - sum);
}
int main(int argc, char **argv)
{
    uint8_t original[65536], changed[65536];
    uint8_t smbios[] = {1,6,0,0,0,1,'K','5','3','S','J',0,0,127,4,0,0,0,0};
    struct k53_acpi_ports ports;
    FILE *f;
    size_t n;
    assert(argc == 2);
    f = fopen(argv[1], "rb");
    assert(f);
    n = fread(original, 1, sizeof(original), f);
    fclose(f);
    assert(k53_parse_fadt(original, n, &ports) == 0);
    assert(ports.smi == 0xb2 && ports.enable == 0xa0 && ports.pm1a == 0x404);
    assert(k53_parse_fadt(original, n - 1, &ports) != 0);
    memcpy(changed, original, n);
    changed[52] ^= 1;
    assert(k53_parse_fadt(changed, n, &ports) == 3);
    fix_checksum(changed, n);
    assert(k53_parse_fadt(changed, n, &ports) == 6);
    memcpy(changed, original, n);
    changed[64] ^= 1;
    fix_checksum(changed, n);
    assert(k53_parse_fadt(changed, n, &ports) == 7);
    memcpy(changed, original, n);
    changed[172] = 0; /* System memory is not supported by this experiment. */
    fix_checksum(changed, n);
    assert(k53_parse_fadt(changed, n, &ports) == 8);
    assert(k53_smbios_product(smbios, sizeof(smbios)));
    assert(!k53_smbios_product(smbios, 11));
    smbios[10] = 'X';
    assert(!k53_smbios_product(smbios, sizeof(smbios)));
    puts("PASS: supported FADT fixture; reject truncation/checksum/command/port/GAS mismatches; SMBIOS product bounds.");
    return 0;
}
