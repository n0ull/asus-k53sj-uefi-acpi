# SPDX-License-Identifier: MIT
"""Synthetic PE fixture: relocation changes match; real code changes do not."""
from pathlib import Path
import json
import struct
import subprocess
import sys


repo = Path(__file__).resolve().parents[1]
work = repo / 'build/research/runtime-inventory/matching-tests'
dump = work / 'dump'
module = dump / 'SyntheticRuntime'
module.mkdir(parents=True, exist_ok=True)
data = bytearray(0x800)
data[:2] = b'MZ'
struct.pack_into('<I', data, 60, 0x80)
data[0x80:0x84] = b'PE\0\0'
struct.pack_into('<HH', data, 0x84, 0x8664, 2)
struct.pack_into('<H', data, 0x94, 240)
optional = 0x98
struct.pack_into('<H', data, optional, 0x20b)
struct.pack_into('<I', data, optional + 16, 0x1000)
struct.pack_into('<II', data, optional + 152, 0x2000, 12)
struct.pack_into('<IIII', data, optional + 240 + 8, 0x200, 0x1000, 0x200, 0x400)
struct.pack_into('<IIII', data, optional + 280 + 8, 0x200, 0x2000, 0x200, 0x600)
data[0x400:0x440] = bytes(range(64))
struct.pack_into('<IIHH', data, 0x600, 0x1000, 12, 0xa010, 0)
(module / 'body.bin').write_bytes(data)
matcher = repo / 'research/linux/match-runtime-inventory.py'


def match(code):
    report = work / 'report.txt'
    report.write_text('IMAGE 0 base=100000 size=3000 fixups=0 handle=0\n'
                      'PE entry_rva=1000\nENTRY64: ' + code.hex(' ') + '\n')
    return json.loads(subprocess.check_output([sys.executable, str(matcher), str(report), str(dump)]))['images'][0]


code = bytearray(data[0x400:0x440])
code[16:24] = b'RELOCATE'
assert match(code)['verdict'] == 'unique-signature'
code[0] ^= 1
assert match(code)['verdict'] == 'unmatched'
assert match(b'\0' * 63)['verdict'] == 'unmatched'
print('PASS: DIR64 masking, code mismatch, and short signature rejection')
