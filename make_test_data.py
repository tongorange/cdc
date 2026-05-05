#!/usr/bin/env python3
"""Generate test files for dedup experiments. Run: python make_test_data.py"""

import random
import hashlib
from pathlib import Path

OUT_DIR = Path("test_data")
OUT_DIR.mkdir(exist_ok=True)

def make_base():
    pattern = b'ABCD' * 1024   # 4KB repeating pattern
    size = 4 * 1024 * 1024
    data = (pattern * (size // len(pattern))) + pattern[:size % len(pattern)]
    (OUT_DIR / "base.bin").write_bytes(data)
    print("Generated base.bin")

def make_identical():
    (OUT_DIR / "same_as_base.bin").write_bytes((OUT_DIR / "base.bin").read_bytes())
    print("Generated same_as_base.bin")

def make_prefix_insert():
    orig = (OUT_DIR / "base.bin").read_bytes()
    (OUT_DIR / "inserted_prefix.bin").write_bytes(b'X'*100 + orig)
    print("Generated inserted_prefix.bin")

def make_middle_insert():
    orig = (OUT_DIR / "base.bin").read_bytes()
    mid = len(orig)//2
    (OUT_DIR / "inserted_middle.bin").write_bytes(orig[:mid] + b'Y'*100 + orig[mid:])
    print("Generated inserted_middle.bin")

def make_random():
    random.seed(42)
    data = bytes(random.getrandbits(8) for _ in range(4*1024*1024))
    (OUT_DIR / "random.bin").write_bytes(data)
    print("Generated random.bin")

if __name__ == "__main__":
    make_base()
    make_identical()
    make_prefix_insert()
    make_middle_insert()
    make_random()
    print("\nSHA-256 checksums:")
    for f in OUT_DIR.glob("*.bin"):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        print(f"{f.name}: {h}")