#!/usr/bin/env python3
"""Generate scenario and scale datasets for dedup experiments."""

import argparse
import hashlib
import random
import shutil
from pathlib import Path

DEFAULT_OUT_DIR = Path("test_data")
MB = 1024 * 1024
PREFIX_INSERT_BYTES = b"CDC_SHIFT_HEADER_" * 9 + b"XYZ"
DELETE_SHIFT_SIZE = 12_345


def build_deterministic_bytes(size: int, seed: int) -> bytes:
    rng = random.Random(seed)
    data = bytearray()
    while len(data) < size:
        segment_size = rng.randint(2048, 24576)
        segment = bytearray(rng.getrandbits(8) for _ in range(segment_size))
        if rng.random() < 0.2:
            marker = f"SEGMENT-{seed}-{len(data):08d}".encode("ascii")
            start = min(len(segment) // 2, max(0, len(segment) - len(marker)))
            segment[start : start + len(marker)] = marker
        data.extend(segment)
    return bytes(data[:size])


def write_structured_file(path: Path, size_mb: int, seed: int) -> None:
    size = size_mb * MB
    data = build_deterministic_bytes(size, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_random_file(path: Path, size_mb: int, seed: int) -> None:
    rng = random.Random(seed)
    data = bytes(rng.getrandbits(8) for _ in range(size_mb * MB))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_scenario_datasets(root: Path, base_size_mb: int) -> None:
    scenarios_root = root / "scenarios"
    if scenarios_root.exists():
        shutil.rmtree(scenarios_root)
    scenarios_root.mkdir(parents=True, exist_ok=True)

    base_data_path = root / "_base.bin"
    write_structured_file(base_data_path, base_size_mb, seed=20240506)
    base_bytes = base_data_path.read_bytes()

    a_root = scenarios_root / "A_no_duplicate"
    write_random_file(a_root / "A1.bin", base_size_mb, 11)
    write_random_file(a_root / "A2.bin", base_size_mb, 12)
    write_random_file(a_root / "A3.bin", base_size_mb, 13)

    b_root = scenarios_root / "B_full_duplicate"
    for name in ("B1.bin", "B2.bin", "B3.bin", "B4.bin"):
        (b_root / name).parent.mkdir(parents=True, exist_ok=True)
        (b_root / name).write_bytes(base_bytes)

    c_root = scenarios_root / "C_local_modify"
    (c_root / "C1.bin").parent.mkdir(parents=True, exist_ok=True)
    (c_root / "C1.bin").write_bytes(base_bytes)
    modified = bytearray(base_bytes)
    offset = min(500_000, len(modified) // 2)
    modified[offset : offset + len(b"MODIFIED_DATA")] = b"MODIFIED_DATA"
    (c_root / "C2.bin").write_bytes(bytes(modified))

    d_root = scenarios_root / "D_prefix_insert"
    (d_root / "D1.bin").parent.mkdir(parents=True, exist_ok=True)
    (d_root / "D1.bin").write_bytes(base_bytes)
    (d_root / "D2.bin").write_bytes(PREFIX_INSERT_BYTES + base_bytes)

    e_root = scenarios_root / "E_delete_shift"
    (e_root / "E1.bin").parent.mkdir(parents=True, exist_ok=True)
    (e_root / "E1.bin").write_bytes(base_bytes)
    delete_start = min(500_000, len(base_bytes) // 2)
    delete_end = min(delete_start + DELETE_SHIFT_SIZE, len(base_bytes))
    deleted = base_bytes[:delete_start] + base_bytes[delete_end:]
    (e_root / "E2.bin").write_bytes(deleted)

    base_data_path.unlink(missing_ok=True)


def build_scale_datasets(root: Path, sizes_mb: list[int]) -> None:
    scales_root = root / "scales"
    if scales_root.exists():
        shutil.rmtree(scales_root)
    scales_root.mkdir(parents=True, exist_ok=True)

    for size_mb in sizes_mb:
        scale_root = scales_root / f"size_{size_mb}mb"
        write_structured_file(scale_root / "base.bin", size_mb, seed=20240506 + size_mb)
        base_bytes = (scale_root / "base.bin").read_bytes()
        (scale_root / "same_as_base.bin").write_bytes(base_bytes)
        (scale_root / "prefix_insert.bin").write_bytes(PREFIX_INSERT_BYTES + base_bytes)


def print_hashes(root: Path) -> None:
    print("\nSHA-256 checksums:")
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{rel}: {digest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate datasets for dedup experiments")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--base-size-mb", type=int, default=4, help="Base size for scenario datasets")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for legacy_file in args.out_dir.glob("*.bin"):
        legacy_file.unlink()

    build_scenario_datasets(args.out_dir, args.base_size_mb)
    build_scale_datasets(args.out_dir, [10, 50, 100])
    print(f"Generated datasets under {args.out_dir}")
    print_hashes(args.out_dir)


if __name__ == "__main__":
    main()
