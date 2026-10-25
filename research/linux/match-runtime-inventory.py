# SPDX-License-Identifier: MIT
"""Match entry signatures in an inventory to extracted PE images, read-only.

Usage: python3 match-runtime-inventory.py REPORT.TXT EXTRACTED_DUMP
Masks DIR64 relocation locations; multiple matches remain explicitly ambiguous.
"""
from pathlib import Path
import json
import re
import struct
import sys


def signature(data):
    if len(data) < 64 or data[:2] != b'MZ':
        return None
    pe = struct.unpack_from('<I', data, 60)[0]
    if pe + 64 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        return None
    optional = pe + 24
    if struct.unpack_from('<H', data, optional)[0] != 0x20b:
        return None
    count = struct.unpack_from('<H', data, pe + 6)[0]
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    if optional_size < 160 or optional + optional_size + 40 * count > len(data):
        return None
    entry = struct.unpack_from('<I', data, optional + 16)[0]
    sections = [struct.unpack_from('<IIII', data, optional + optional_size + 40 * i + 8)
                for i in range(count)]

    def offset(rva, size):
        for _, start, length, raw in sections:
            if start <= rva and rva - start + size <= length and raw + rva - start + size <= len(data):
                return raw + rva - start
        return None

    at = offset(entry, 64)
    if at is None:
        return None
    code = data[at:at + 64]
    mask = bytearray([1] * 64)
    reloc, size = struct.unpack_from('<II', data, optional + 112 + 5 * 8)
    pos = 0
    while pos + 8 <= size:
        block = offset(reloc + pos, 8)
        if block is None:
            return None
        page, length = struct.unpack_from('<II', data, block)
        if length < 8 or length % 2 or length > size - pos:
            return None
        block = offset(reloc + pos, length)
        if block is None:
            return None
        for index in range(8, length, 2):
            item = struct.unpack_from('<H', data, block + index)[0]
            if item >> 12 != 10:
                continue
            target = page + (item & 0xfff)
            for i in range(max(0, target - entry), min(64, target + 8 - entry)):
                mask[i] = 0
        pos += length
    return entry, code, mask


def main():
    report = Path(sys.argv[1]).read_text(errors='replace')
    dump = Path(sys.argv[2]).resolve(strict=True)
    candidates = []
    for path in sorted(dump.rglob('body.bin')):
        value = signature(path.read_bytes())
        if value:
            candidates.append((str(path.relative_to(dump)), *value))
    pattern = (r'IMAGE (\d+) base=([0-9A-Fa-f]+) size=([0-9A-Fa-f]+)[^\n]*\s+'
               r'PE entry_rva=([0-9A-Fa-f]+)\s+ENTRY64:([ 0-9A-Fa-f]+)')
    output = []
    for found in re.finditer(pattern, report):
        index, base, size, ep, raw = found.groups()
        actual = bytes.fromhex(raw)
        matches = [name for name, entry, code, mask in candidates
                   if entry == int(ep, 16) and len(actual) == 64
                   and sum(mask) >= 32 and all(not mask[i] or actual[i] == code[i] for i in range(64))]
        output.append({'image': int(index), 'base': base, 'size': size,
                       'entry_rva': ep, 'candidate_paths': matches,
                       'verdict': 'unique-signature' if len(matches) == 1 else
                                  'ambiguous' if matches else 'unmatched'})
    print(json.dumps({'note': 'Entry signature match only; not full image integrity verification',
                      'images': output}, indent=2))


if __name__ == '__main__':
    main()
