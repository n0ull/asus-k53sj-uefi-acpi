# SPDX-License-Identifier: MIT
"""Generate a synthetic FADT with the supported K53SJ register layout.

This contains no captured firmware bytes or machine identifiers. The parser
was also tested against the owner's real FADT during the original investigation.
"""
from pathlib import Path
import struct
import sys


def main():
    data = bytearray(244)
    data[:4] = b"FACP"
    struct.pack_into("<I", data, 4, len(data))
    data[8] = 4
    data[10:16] = b"_ASUS_"
    data[16:24] = b"NoteBook"
    struct.pack_into("<I", data, 48, 0xB2)
    data[52] = 0xA0
    data[53] = 0xA1
    struct.pack_into("<I", data, 64, 0x404)
    data[89] = 2
    data[172] = 1  # System I/O GAS
    data[173] = 16
    struct.pack_into("<Q", data, 176, 0x404)
    data[9] = (-sum(data)) & 0xFF
    Path(sys.argv[1]).write_bytes(data)


if __name__ == "__main__":
    main()
