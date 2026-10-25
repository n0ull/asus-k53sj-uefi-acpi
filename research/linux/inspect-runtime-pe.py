# SPDX-License-Identifier: MIT
"""Read-only index of local extracted firmware PE files; no firmware execution.

Usage: python3 research/linux/inspect-runtime-pe.py local/firmware-analysis/K53SJAS.315.dump
Prints JSON to stdout. GUID hits are byte references, not proof of protocol ownership.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
import uuid


GUIDS = {
    'runtime_arch': 'b7dfb4e1-052f-449f-87be-9818fc91b733',
    'acpi_shared_unknown': '34cf7ec3-50f4-4544-8f50-fb1f9ff60748',
}


def inspect(path):
    data = path.read_bytes()
    if data[:2] != b'MZ' or len(data) < 64:
        return None
    pe = struct.unpack_from('<I', data, 60)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        return None
    machine, sections = struct.unpack_from('<HH', data, pe + 4)
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    optional = pe + 24
    if optional_size < 32 or optional + optional_size + sections * 40 > len(data):
        return None
    magic = struct.unpack_from('<H', data, optional)[0]
    if magic != 0x20b:
        return None
    ranges = []
    for index in range(sections):
        at = optional + optional_size + index * 40
        virtual_size, rva, size, offset = struct.unpack_from('<IIII', data, at + 8)
        ranges.append((offset, min(offset + size, len(data)), rva))

    def location(offset):
        rva = next((base + offset - start for start, end, base in ranges
                    if start <= offset < end), None)
        return {'file_offset': hex(offset), 'rva': hex(rva) if rva is not None else None}

    hits = {}
    for name, value in GUIDS.items():
        needle = uuid.UUID(value).bytes_le
        offsets = []
        start = 0
        while (found := data.find(needle, start)) != -1:
            offsets.append(location(found))
            start = found + 1
        if offsets:
            hits[name] = offsets
    if not hits:
        return None
    return {'path': str(path), 'machine': hex(machine),
            'sha256': hashlib.sha256(data).hexdigest(), 'references': hits}


root = Path(sys.argv[1]).resolve(strict=True)
result = []
for path in sorted(root.rglob('body.bin')):
    item = inspect(path)
    if item:
        result.append(item)
print(json.dumps({'warning': 'Literal references only; not ownership or execution evidence',
                  'modules': result}, indent=2))
