# SPDX-License-Identifier: MIT
"""Add opt-in, single-position ACPI probes to the existing diag2 source.

The generated diff modifies GPL kernel code; it is not relicensed by this script.
"""
from pathlib import Path
import difflib
import sys

root = Path(sys.argv[1])
path = root / 'arch/x86/platform/efi/efi.c'
before = path.read_text()
if 'k53diag_acpi_phase' in before:
    raise SystemExit('Phase probe already present; use the existing source or a fresh cache.')
assert 'K53DIAG E05 SetVirtualAddressMap RETURN' in before, 'Apply the diag2 patch first'
text = before.replace('#include <linux/bcd.h>', '#include <linux/bcd.h>\n#include <linux/acpi.h>\n#include <linux/dmi.h>')
anchor = 'static unsigned long efi_systab_phys __initdata;'
assert text.count(anchor) == 1
helpers = r'''
/* Experimental single-position probes, not a production firmware quirk. */
enum k53_acpi_phase {
	K53_PHASE_NONE,
	K53_PHASE_PRE_SVAM,
	K53_PHASE_POST_SVAM,
	K53_PHASE_PRE_DUMMY,
	K53_PHASE_POST_DUMMY,
};
static enum k53_acpi_phase k53_phase __initdata;
static bool k53_skip_dummy __initdata;

static int __init k53_phase_setup(char *arg)
{
	if (!arg)
		return -EINVAL;
	if (!strcmp(arg, "pre_svam"))
		k53_phase = K53_PHASE_PRE_SVAM;
	else if (!strcmp(arg, "post_svam"))
		k53_phase = K53_PHASE_POST_SVAM;
	else if (!strcmp(arg, "pre_dummy"))
		k53_phase = K53_PHASE_PRE_DUMMY;
	else if (!strcmp(arg, "post_dummy"))
		k53_phase = K53_PHASE_POST_DUMMY;
	else
		return -EINVAL;
	return 0;
}
early_param("k53diag_acpi_phase", k53_phase_setup);

static int __init k53_skip_dummy_setup(char *arg)
{
	k53_skip_dummy = true;
	return 0;
}
early_param("k53diag_skip_dummy", k53_skip_dummy_setup);

static void __init k53_acpi_probe(enum k53_acpi_phase phase, const char *name)
{
	acpi_status status, sci_status;
	u32 sci = ~0U;

	if (k53_phase != phase)
		return;
	if (acpi_disabled || !dmi_match(DMI_PRODUCT_NAME, "K53SJ")) {
		pr_emerg("K53PHASE %s REFUSED: ACPI disabled or product is not K53SJ\n", name);
		return;
	}
	pr_emerg("K53PHASE %s ENTER EFI_DBG=%u\n", name, efi_enabled(EFI_DBG));
	sci_status = acpi_read_bit_register(ACPI_BITREG_SCI_ENABLE, &sci);
	pr_emerg("K53PHASE %s BEFORE SCI_EN=%u sci_status=%#x\n", name, sci, sci_status);
	status = acpi_enable();
	sci_status = acpi_read_bit_register(ACPI_BITREG_SCI_ENABLE, &sci);
	pr_emerg("K53PHASE %s RETURN acpi_status=%#x SCI_EN=%u sci_status=%#x\n",
		 name, status, sci, sci_status);
}
'''.replace('\\t', '\t')
# Raw literals preserve C escape sequences.
text = text.replace(anchor, helpers + '\n' + anchor)
anchor = '\tpr_emerg("K53DIAG E05 SetVirtualAddressMap ENTER\\n");'
assert text.count(anchor) == 1
text = text.replace(anchor, '\tk53_acpi_probe(K53_PHASE_PRE_SVAM, "PRE_SVAM");\n' + anchor)
anchor = '\tefi_check_for_embedded_firmwares();'
assert text.count(anchor) == 1
text = text.replace(anchor, '\tk53_acpi_probe(K53_PHASE_POST_SVAM, "POST_SVAM");\n' + anchor)
anchor = '\tefi_delete_dummy_variable();'
assert text.count(anchor) == 1
text = text.replace(anchor, '''\tk53_acpi_probe(K53_PHASE_PRE_DUMMY, "PRE_DUMMY");
\tif (k53_skip_dummy)
\t\tpr_emerg("K53PHASE DUMMY_DELETE SKIPPED (SVAM/runtime otherwise retained)\\n");
\telse
\t\tefi_delete_dummy_variable();
\tk53_acpi_probe(K53_PHASE_POST_DUMMY, "POST_DUMMY");''')
path.write_text(text)
patch = ''.join(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
                                    fromfile='a/arch/x86/platform/efi/efi.c',
                                    tofile='b/arch/x86/platform/efi/efi.c'))
(root.parent / 'linux-7.2.7-stage3-extra.patch').write_text(patch)
print('Added opt-in skip-DUMMY and single-position ACPI phase probes.')
