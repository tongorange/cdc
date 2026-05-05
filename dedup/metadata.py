import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class MetadataStore:
    """Manage file-to-chunks mapping in <root>/files.json"""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.root / "files.json"
        self.data = self._load()

    def _load(self) -> dict:
        if not self.meta_file.exists():
            return {"next_file_id": 1, "files": {}}
        with open(self.meta_file, "r") as f:
            return json.load(f)

    def _save(self):
        with open(self.meta_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def add_file(self, filename: str, original_path: str, size: int, chunking: str, chunks: List[str]) -> str:
        if size < 0:
            raise ValueError("size cannot be negative")
        if chunking not in ("fixed", "cdc"):
            raise ValueError("chunking must be 'fixed' or 'cdc'")
        if not all(isinstance(c, str) for c in chunks):
            raise TypeError("chunks must be list of strings")

        file_id = str(self.data["next_file_id"])
        self.data["files"][file_id] = {
            "filename": filename,
            "original_path": original_path,
            "size": size,
            "chunking": chunking,
            "chunks": chunks,
            "created_at": datetime.now().isoformat(),
        }
        self.data["next_file_id"] += 1
        self._save()
        return file_id

    def get_file(self, file_id: str) -> dict:
        if file_id not in self.data["files"]:
            raise KeyError(f"File ID {file_id} not found")
        return self.data["files"][file_id]

    def list_files(self) -> Dict[str, dict]:
        return self.data["files"].copy()

    def get_all_chunks(self) -> List[str]:
        """Return all chunk hashes referenced by stored files (for stats)."""
        chunks = []
        for meta in self.data["files"].values():
            chunks.extend(meta["chunks"])
        return chunks