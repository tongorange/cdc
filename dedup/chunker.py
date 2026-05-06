import math
from pathlib import Path
from typing import Iterator

try:
    import fastcdc  # type: ignore
except ImportError:  # pragma: no cover - covered via fallback tests
    fastcdc = None

def fixed_chunk_file(path: Path, chunk_size: int = 4096) -> Iterator[bytes]:
    """Fixed-size chunk iterator."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

def cdc_chunk_file(
    path: Path,
    min_size: int = 2048,
    avg_size: int = 4096,
    max_size: int = 8192,
    window_size: int = 48,
) -> Iterator[bytes]:
    """Content-defined chunking with a fastcdc backend or a pure Python fallback."""
    if min_size <= 0 or avg_size <= 0 or max_size <= 0:
        raise ValueError("chunk sizes must be positive")
    if not (min_size <= avg_size <= max_size):
        raise ValueError("expected min_size <= avg_size <= max_size")
    if window_size <= 0:
        raise ValueError("window_size must be positive")

    if fastcdc is not None:
        for chunk in fastcdc.iter_chunks(str(path), avg_size, min_size, max_size):
            yield chunk.data
        return

    yield from _cdc_chunk_file_fallback(path, min_size, avg_size, max_size, window_size)


def _cdc_chunk_file_fallback(
    path: Path,
    min_size: int,
    avg_size: int,
    max_size: int,
    window_size: int,
) -> Iterator[bytes]:
    """Pure Python CDC fallback based on a lightweight rolling hash boundary."""
    data = Path(path).read_bytes()
    if not data:
        return

    boundary_bits = max(1, round(math.log2(avg_size)))
    mask = (1 << boundary_bits) - 1
    rolling_hash = 0
    chunk_start = 0

    for index, byte in enumerate(data):
        rolling_hash = ((rolling_hash << 1) + byte + 1) & 0xFFFFFFFF
        chunk_len = index - chunk_start + 1
        if chunk_len < min_size:
            continue

        boundary_hit = (rolling_hash & mask) == 0
        if chunk_len >= max_size or boundary_hit:
            yield data[chunk_start : index + 1]
            chunk_start = index + 1
            rolling_hash = 0

    if chunk_start < len(data):
        yield data[chunk_start:]
