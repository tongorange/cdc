from pathlib import Path
from typing import Iterator
import fastcdc

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
    window_size: int = 48,   # unused in fastcdc, kept for compatibility
) -> Iterator[bytes]:
    """Content-Defined Chunking using fastcdc library."""
    # fastcdc.iter_chunks returns an iterator of Chunk objects
    for chunk in fastcdc.iter_chunks(str(path), avg_size, min_size, max_size):
        yield chunk.data