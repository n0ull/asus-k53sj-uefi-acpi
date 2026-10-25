# SPDX-License-Identifier: MIT
"""Opt-in temporary RAM-only slot38 experiment; never a production kernel fix."""
from pathlib import Path
import difflib
import sys

root = Path(sys.argv[1])
path = root / 'arch/x86/platform/efi/efi.c'
before = path.read_text()
assert 'k53diag_ec_watch' in before and 'k53diag_ec_restore38' not in before
header = Path(__file__).with_name('ec_slot_guard.h')
(path.parent / header.name).write_bytes(header.read_bytes())
helper = r'''
/* Controlled RAM-only intervention; no flash, NVRAM, or disk changes. */
static bool k53_ec_restore38_enabled __initdata;
static bool k53_ec_slot38_applied __initdata;
static int __init k53_ec_restore38_setup(char *arg)
{
	k53_ec_restore38_enabled = true;
	return 0;
}
early_param("k53diag_ec_restore38", k53_ec_restore38_setup);

static void __init k53_ec_slot38_experiment(bool cleanup)
{
	u64 observed[9], wanted;
	void *mapping;
	if (!k53_ec_restore38_enabled)
		return;
	if (cleanup && !k53_ec_slot38_applied)
		return;
	if (!k53_ec_watch_enabled || !k53_ec_base ||
	    k53_phase != K53_PHASE_POST_SVAM ||
	    !dmi_match(DMI_PRODUCT_NAME, "K53SJ")) {
		pr_emerg("K53SLOT38 REFUSED: prerequisites not met\n");
		return;
	}
	mapping = memremap(k53_ec_base + 0x1e70, sizeof(observed), MEMREMAP_WB);
	if (!mapping) {
		pr_emerg("K53SLOT38 REFUSED: mapping failed\n");
		return;
	}
	memcpy(observed, mapping, sizeof(observed));
	if (!k53_ec_slot_guard(k53_ec_base, k53_ec_before, k53_ec_expected,
			       observed, cleanup)) {
		pr_emerg("K53SLOT38 REFUSED: nine-slot validation failed cleanup=%u\n", cleanup);
		memunmap(mapping);
		return;
	}
	wanted = cleanup ? k53_ec_expected[7] : k53_ec_before[7];
	pr_emerg("K53SLOT38 %s ENTER addr=%#llx old=%#llx new=%#llx RAM_ONLY\n",
		 cleanup ? "CLEANUP" : "APPLY", k53_ec_base + 0x1ea8, observed[7], wanted);
	WRITE_ONCE(((u64 *)mapping)[7], wanted);
	mb();
	observed[7] = READ_ONCE(((u64 *)mapping)[7]);
	k53_ec_slot38_applied = !cleanup;
	pr_emerg("K53SLOT38 %s RETURN readback=%#llx match=%u\n",
		 cleanup ? "CLEANUP" : "APPLY", observed[7], observed[7] == wanted);
	memunmap(mapping);
}
'''
anchor = 'static unsigned long efi_systab_phys __initdata;'
assert before.count(anchor) == 1
text = before.replace(anchor, helper + '\n' + anchor)
text = text.replace('#include <linux/unaligned.h>', '#include <linux/unaligned.h>\n#include "ec_slot_guard.h"')
anchor = '\tk53_acpi_probe(K53_PHASE_POST_SVAM, "POST_SVAM");'
assert text.count(anchor) == 1
text = text.replace(anchor, '\tk53_ec_slot38_experiment(false);\n' + anchor +
                    '\n\tk53_ec_slot38_experiment(true);')
path.write_text(text)
(root.parent / 'linux-7.2.7-slot38-extra.patch').write_text(''.join(difflib.unified_diff(
    before.splitlines(True), text.splitlines(True), fromfile='a/arch/x86/platform/efi/efi.c',
    tofile='b/arch/x86/platform/efi/efi.c')))
print('Added opt-in slot38 RAM-only apply/probe/cleanup experiment.')
