/* SPDX-License-Identifier: MIT */
/* Decision seam shared by the diagnostic kernel and native guard tests. */
#ifndef K53_EC_SLOT_GUARD_H
#define K53_EC_SLOT_GUARD_H
static int k53_ec_slot_guard(unsigned long long base,
                            const unsigned long long before[9],
                            const unsigned long long expected[9],
                            const unsigned long long observed[9], int cleanup)
{
    static const unsigned long long offsets[9] = {
        0xb4c, 0xc00, 0xc24, 0xc4c, 0xc68, 0xcc8, 0xd44, 0xe74, 0xed4
    };
    unsigned int i;
    if (!base || base > (~0ULL) - 0x27e0)
        return 0;
    for (i = 0; i < 9; ++i) {
        unsigned long long wanted = cleanup && i == 7 ? before[i] : expected[i];
        if (before[i] != base + offsets[i] || !expected[i] || expected[i] == before[i] ||
            observed[i] != wanted)
            return 0;
    }
    return 1;
}
#endif
