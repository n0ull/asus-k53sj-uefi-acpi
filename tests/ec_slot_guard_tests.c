// SPDX-License-Identifier: MIT
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../research/linux/ec_slot_guard.h"
int main(void)
{
    const unsigned long long base = 0xaad49000;
    const unsigned long long offsets[9] = {0xb4c,0xc00,0xc24,0xc4c,0xc68,0xcc8,0xd44,0xe74,0xed4};
    unsigned long long before[9], expected[9], current[9];
    unsigned int i;
    for (i = 0; i < 9; ++i) {
        before[i] = base + offsets[i];
        expected[i] = 0xfffffffef6949000ULL + offsets[i];
        current[i] = expected[i];
    }
    assert(k53_ec_slot_guard(base,before,expected,current,0));
    assert(!k53_ec_slot_guard(base,before,expected,current,1));
    current[7] = before[7];
    assert(k53_ec_slot_guard(base,before,expected,current,1));
    assert(!k53_ec_slot_guard(base,before,expected,current,0));
    current[8] = before[8];
    assert(!k53_ec_slot_guard(base,before,expected,current,1));
    memcpy(current,expected,sizeof(current));
    current[0] ^= 1;
    assert(!k53_ec_slot_guard(base,before,expected,current,0));
    memcpy(current,expected,sizeof(current));
    assert(!k53_ec_slot_guard(0,before,expected,current,0));
    before[0] ^= 1;
    assert(!k53_ec_slot_guard(base,before,expected,current,0));
    puts("PASS: apply/cleanup state, unrelated slot mismatch, null base, wrong initial table");
    return 0;
}
