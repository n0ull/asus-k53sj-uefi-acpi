# SPDX-License-Identifier: MIT
"""Compare two UEFIExtract dumps by FFS GUID and decompressed PE payloads.

Usage: python3 compare-firmware.py OLD_DUMP NEW_DUMP
No firmware execution or rewriting. JSON output deliberately excludes binary data.
"""
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import re
import struct
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


if len(sys.argv) == 4 and sys.argv[1] == '--images':
    a, b = (Path(p).read_bytes() for p in sys.argv[2:])
    common = min(len(a), len(b))
    blocks = [offset for offset in range(0, common, 4096)
              if a[offset:offset + 4096] != b[offset:offset + 4096]]
    ranges = []
    for offset in blocks:
        if ranges and ranges[-1][1] == offset:
            ranges[-1][1] = offset + 4096
        else:
            ranges.append([offset, offset + 4096])
    print(json.dumps({'old_size': len(a), 'new_size': len(b),
                      'old_sha256': digest(a), 'new_sha256': digest(b),
                      'different_bytes': sum(x != y for x, y in zip(a, b)),
                      'prefix_0_to_90000_different_bytes': sum(x != y for x, y in zip(a[:0x90000], b[:0x90000])),
                      'different_4k_ranges': [[hex(x), hex(y)] for x, y in ranges]}, indent=2))
    raise SystemExit(0)


def pe_sections(data):
    if len(data) < 64 or data[:2] != b'MZ':
        return {}
    pe = struct.unpack_from('<I', data, 60)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        return {}
    count = struct.unpack_from('<H', data, pe + 6)[0]
    optional = struct.unpack_from('<H', data, pe + 20)[0]
    start = pe + 24 + optional
    if start + count * 40 > len(data):
        return {}
    result = {}
    for i in range(count):
        at = start + i * 40
        name = data[at:at + 8].rstrip(b'\0').decode('ascii', errors='replace')
        size, offset = struct.unpack_from('<II', data, at + 16)
        if offset + size <= len(data):
            result[name] = {'size': size, 'sha256': digest(data[offset:offset + size])}
    return result


def inventory(root):
    entries = defaultdict(list)
    for info in sorted(root.rglob('info.txt')):
        text = info.read_text(errors='replace')
        guid = re.search(r'^File GUID: (.+)$', text, re.M)
        if not text.startswith('Type: File\n') or not guid:
            continue
        parent = info.parent
        body = parent / 'body.bin'
        name = re.search(r'^Text: (.+)$', text, re.M)
        item = {'name': name.group(1) if name else parent.name,
                'path': str(parent.relative_to(root)),
                'body_sha256': digest(body.read_bytes()) if body.exists() else None,
                'pe': []}
        for child in sorted(parent.rglob('info.txt')):
            metadata = child.read_text(errors='replace')
            if not re.search(r'^Subtype: (PE32|TE) image$', metadata, re.M):
                continue
            # A volume-container FFS is not the owner of nested FFS executables.
            if any((p / 'info.txt').exists() and
                   (p / 'info.txt').read_text(errors='replace').startswith('Type: File\n')
                   for p in child.parent.parents if p != parent and parent in p.parents):
                continue
            payload = child.parent / 'body.bin'
            if payload.exists():
                data = payload.read_bytes()
                item['pe'].append({'size': len(data), 'sha256': digest(data),
                                   'sections': pe_sections(data)})
        entries[guid.group(1)].append(item)
    return entries


old = inventory(Path(sys.argv[1]).resolve(strict=True))
new = inventory(Path(sys.argv[2]).resolve(strict=True))
rows = []
for guid in sorted(set(old) | set(new)):
    a, b = old.get(guid, []), new.get(guid, [])
    body_same = sorted(x['body_sha256'] or '' for x in a) == sorted(x['body_sha256'] or '' for x in b)
    pe_a = sorted(p['sha256'] for x in a for p in x['pe'])
    pe_b = sorted(p['sha256'] for x in b for p in x['pe'])
    rows.append({'guid': guid, 'names': sorted(set(x['name'] for x in a + b)),
                 'status': 'added' if not a else 'removed' if not b else
                           'identical-body' if body_same else 'changed-body',
                 'pe_status': 'identical' if pe_a == pe_b and pe_a else
                              'different' if pe_a != pe_b else 'no-pe',
                 'old': a, 'new': b})
print(json.dumps({'old_files': sum(map(len, old.values())), 'new_files': sum(map(len, new.values())),
                  'rows': rows}, indent=2))
