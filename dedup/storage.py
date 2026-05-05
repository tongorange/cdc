from pathlib import Path
import os

class ChunkStore:
    """Store unique chunks in <root>/chunks/xx/xxxxxxxx..."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.chunks_dir = self.root / "chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    def _validate_hash(self, chunk_hash: str) -> None:
        if not isinstance(chunk_hash, str) or len(chunk_hash) != 64 or not all(c in "0123456789abcdef" for c in chunk_hash):
            raise ValueError("Invalid chunk hash")

    def chunk_path(self, chunk_hash: str) -> Path:
        self._validate_hash(chunk_hash)
        return self.chunks_dir / chunk_hash[:2] / chunk_hash

    def has_chunk(self, chunk_hash: str) -> bool:
        self._validate_hash(chunk_hash)
        return self.chunk_path(chunk_hash).is_file()

    def put_chunk(self, chunk_hash: str, data: bytes) -> bool:
        """Return True if new chunk was written, False if already existed."""
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        path = self.chunk_path(chunk_hash)
        if path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return True

    def get_chunk(self, chunk_hash: str) -> bytes:
        self._validate_hash(chunk_hash)
        path = self.chunk_path(chunk_hash)
        if not path.exists():
            raise FileNotFoundError(f"Chunk {chunk_hash} not found")
        return path.read_bytes()