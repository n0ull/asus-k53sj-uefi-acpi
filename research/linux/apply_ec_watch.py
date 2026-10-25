# SPDX-License-Identifier: MIT
"""Opt-in read-only EC table snapshots around SVAM; generated kernel diff is GPL."""
from pathlib import Path
import difflib
import sys

root = Path(sys.argv[1])
path = root / 'arch/x86/platform/efi/efi.c'
before = path.read_text()
assert 'K53PHASE POST_SVAM' not in before  # phase helper uses name argument, not this literal
assert 'k53diag_acpi_phase' in before
assert 'k53diag_ec_watch' not in before
anchor = 'static unsigned long efi_systab_phys __initdata;'
assert before.count(anchor) == 1
helper = r'''
/* Read-only experiment, specific to the inventoried K53SJ ECProtocol layout. */
static bool k53_ec_watch_enabled __initdata;
static u64 k53_ec_base __initdata, k53_ec_before[9] __initdata;
static u64 k53_ec_expected[9] __initdata;

static int __init k53_ec_watch_setup(char *arg)
{
	k53_ec_watch_enabled = true;
	return 0;
}
early_param("k53diag_ec_watch", k53_ec_watch_setup);

static bool __init k53_ec_runtime_range(u64 addr, u64 bytes)
{
	efi_memory_desc_t *md;
	if (!addr || !bytes || addr + bytes < addr)
		return false;
	for_each_efi_memory_desc(md) {
		u64 length = md->num_pages << EFI_PAGE_SHIFT;
		if ((md->type == EFI_RUNTIME_SERVICES_CODE ||
		     md->type == EFI_RUNTIME_SERVICES_DATA) &&
		    addr >= md->phys_addr && addr - md->phys_addr < length &&
		    bytes <= length - (addr - md->phys_addr))
			return true;
	}
	return false;
}

static u64 __init k53_ec_virtual(u64 physical)
{
	efi_memory_desc_t *md;
	for_each_efi_memory_desc(md) {
		u64 length = md->num_pages << EFI_PAGE_SHIFT;
		if (physical >= md->phys_addr && physical - md->phys_addr < length)
			return md->virt_addr + physical - md->phys_addr;
	}
	return 0;
}

static void __init k53_ec_snapshot(bool after)
{
	static const u64 offsets[9] = {0xb4c, 0xc00, 0xc24, 0xc4c, 0xc68,
				      0xcc8, 0xd44, 0xe74, 0xed4};
	efi_memory_desc_t *md;
	u64 values[9], candidates = 0, pages = 0;
	void *mapping;
	unsigned int i, changed = 0, translated = 0;

	if (!k53_ec_watch_enabled)
		return;
	if (!dmi_match(DMI_PRODUCT_NAME, "K53SJ")) {
		pr_emerg("K53EC REFUSED: product is not K53SJ\n");
		return;
	}
	if (!after) {
		for_each_efi_memory_desc(md) {
			u64 page;
			if (md->type != EFI_RUNTIME_SERVICES_CODE &&
			    md->type != EFI_RUNTIME_SERVICES_DATA)
				continue;
			for (page = 0; page < md->num_pages && pages < 8192; ++page) {
				u64 base = md->phys_addr + (page << EFI_PAGE_SHIFT);
				u32 pe, entry = 0, image_size = 0;
				bool valid = false;
				++pages;
				mapping = memremap(base, EFI_PAGE_SIZE, MEMREMAP_WB);
				if (!mapping)
					continue;
				if (get_unaligned_le16(mapping) == 0x5a4d) {
					pe = get_unaligned_le32(mapping + 0x3c);
					if (pe <= EFI_PAGE_SIZE - 0x60 &&
					    get_unaligned_le32(mapping + pe) == 0x4550 &&
					    get_unaligned_le16(mapping + pe + 4) == 0x8664 &&
					    get_unaligned_le16(mapping + pe + 24) == 0x20b) {
						entry = get_unaligned_le32(mapping + pe + 40);
						image_size = get_unaligned_le32(mapping + pe + 80);
						valid = entry == 0x2f8 && image_size == 0x27e0;
					}
				}
				memunmap(mapping);
				if (!valid || !k53_ec_runtime_range(base + 0x1e70, sizeof(values)))
					continue;
				mapping = memremap(base + 0x1e70, sizeof(values), MEMREMAP_WB);
				if (!mapping)
					continue;
				memcpy(values, mapping, sizeof(values));
				memunmap(mapping);
				for (i = 0; i < 9; ++i)
					if (values[i] != base + offsets[i])
						break;
				if (i != 9)
					continue;
				++candidates;
				k53_ec_base = base;
				memcpy(k53_ec_before, values, sizeof(values));
			}
		}
		pr_emerg("K53EC PRE candidates=%llu pages=%llu base=%#llx\n",
			 candidates, pages, k53_ec_base);
		if (candidates != 1) {
			k53_ec_base = 0;
			pr_emerg("K53EC STOP: require one exact physical EC table match\n");
			return;
		}
		for (i = 0; i < 9; ++i)
			k53_ec_expected[i] = k53_ec_virtual(k53_ec_before[i]);
		pr_emerg("K53EC PRE slot38=%#llx expected_virtual=%#llx\n",
			 k53_ec_before[7], k53_ec_expected[7]);
		pr_emerg("K53EC PRE slot40=%#llx expected_virtual=%#llx\n",
			 k53_ec_before[8], k53_ec_expected[8]);
		return;
	}
	if (!k53_ec_base)
		return;
	mapping = memremap(k53_ec_base + 0x1e70, sizeof(values), MEMREMAP_WB);
	if (!mapping) {
		pr_emerg("K53EC POST mapping failed\n");
		return;
	}
	memcpy(values, mapping, sizeof(values));
	memunmap(mapping);
	for (i = 0; i < 9; ++i) {
		changed += values[i] != k53_ec_before[i];
		translated += k53_ec_expected[i] && values[i] == k53_ec_expected[i];
	}
	pr_emerg("K53EC POST physical_table=%#llx changed=%u translated=%u/9\n",
		 k53_ec_base + 0x1e70, changed, translated);
	pr_emerg("K53EC POST slot38=%#llx before=%#llx expected_virtual=%#llx\n",
		 values[7], k53_ec_before[7], k53_ec_expected[7]);
	pr_emerg("K53EC POST slot40=%#llx before=%#llx expected_virtual=%#llx\n",
		 values[8], k53_ec_before[8], k53_ec_expected[8]);
}
'''
text = before.replace(anchor, helper + '\n' + anchor)
text = text.replace('#include <linux/bcd.h>', '#include <linux/bcd.h>\n#include <linux/unaligned.h>')
anchor = '\tk53_acpi_probe(K53_PHASE_PRE_SVAM, "PRE_SVAM");'
assert text.count(anchor) == 1
text = text.replace(anchor, '\tk53_ec_snapshot(false);\n' + anchor)
anchor = '\tk53_acpi_probe(K53_PHASE_POST_SVAM, "POST_SVAM");'
assert text.count(anchor) == 1
text = text.replace(anchor, '\tk53_ec_snapshot(true);\n' + anchor)
path.write_text(text)
(root.parent / 'linux-7.2.7-ec-watch-extra.patch').write_text(''.join(difflib.unified_diff(
    before.splitlines(True), text.splitlines(True), fromfile='a/arch/x86/platform/efi/efi.c',
    tofile='b/arch/x86/platform/efi/efi.c')))
print('Added opt-in read-only K53EC snapshots around SVAM.')
