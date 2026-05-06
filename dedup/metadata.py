import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class MetadataStore:
    """Manage file-to-chunks mapping in <root>/files.json"""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.root / "files.json"
        self.data = self._load()

    def _load(self) -> dict:
        if not self.meta_file.exists():
            return {"next_file_id": 1, "next_snapshot_id": 1, "files": {}, "snapshots": {}}
        with open(self.meta_file, "r") as f:
            data = json.load(f)
        data.setdefault("next_file_id", 1)
        data.setdefault("next_snapshot_id", 1)
        data.setdefault("files", {})
        data.setdefault("snapshots", {})
        return data

    def _save(self):
        with open(self.meta_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def _build_file_record(
        self,
        filename: str,
        original_path: str,
        size: int,
        chunking: str,
        chunks: List[str],
        created_at: str | None = None,
        relative_path: str | None = None,
        snapshot_id: str | None = None,
    ) -> dict:
        if size < 0:
            raise ValueError("size cannot be negative")
        if chunking not in ("fixed", "cdc"):
            raise ValueError("chunking must be 'fixed' or 'cdc'")
        if not all(isinstance(c, str) for c in chunks):
            raise TypeError("chunks must be list of strings")

        now = datetime.now().isoformat()
        return {
            "filename": filename,
            "original_path": original_path,
            "size": size,
            "chunking": chunking,
            "chunks": chunks,
            "created_at": created_at or now,
            "updated_at": now,
            "relative_path": relative_path,
            "snapshot_id": snapshot_id,
        }

    def add_file(
        self,
        filename: str,
        original_path: str,
        size: int,
        chunking: str,
        chunks: List[str],
        relative_path: str | None = None,
        snapshot_id: str | None = None,
    ) -> str:
        file_id = str(self.data["next_file_id"])
        self.data["files"][file_id] = self._build_file_record(
            filename=filename,
            original_path=original_path,
            size=size,
            chunking=chunking,
            chunks=chunks,
            relative_path=relative_path,
            snapshot_id=snapshot_id,
        )
        self.data["next_file_id"] += 1
        self._save()
        return file_id

    def get_file(self, file_id: str) -> dict:
        if file_id not in self.data["files"]:
            raise KeyError(f"File ID {file_id} not found")
        return self.data["files"][file_id]

    def list_files(self) -> Dict[str, dict]:
        return self.data["files"].copy()

    def list_snapshots(self) -> Dict[str, dict]:
        return self.data["snapshots"].copy()

    def find_files_by_name(self, filename: str) -> Dict[str, dict]:
        return {
            file_id: meta
            for file_id, meta in self.data["files"].items()
            if meta["filename"] == filename
        }

    def get_snapshot(self, snapshot_id: str) -> dict:
        if snapshot_id not in self.data["snapshots"]:
            raise KeyError(f"Snapshot ID {snapshot_id} not found")
        return self.data["snapshots"][snapshot_id]

    def add_snapshot(
        self,
        source_path: str,
        chunking: str,
        file_ids: List[str],
        file_count: int,
        description: str | None = None,
    ) -> str:
        snapshot_id = str(self.data["next_snapshot_id"])
        now = datetime.now().isoformat()
        self.data["snapshots"][snapshot_id] = {
            "source_path": source_path,
            "chunking": chunking,
            "file_ids": file_ids,
            "file_count": file_count,
            "description": description,
            "created_at": now,
            "updated_at": now,
        }
        self.data["next_snapshot_id"] += 1
        self._save()
        return snapshot_id

    def update_snapshot(
        self,
        snapshot_id: str,
        source_path: str,
        chunking: str,
        file_ids: List[str],
        file_count: int,
        description: str | None = None,
    ) -> dict:
        current = self.get_snapshot(snapshot_id)
        now = datetime.now().isoformat()
        self.data["snapshots"][snapshot_id] = {
            "source_path": source_path,
            "chunking": chunking,
            "file_ids": file_ids,
            "file_count": file_count,
            "description": description,
            "created_at": current.get("created_at", now),
            "updated_at": now,
        }
        self._save()
        return self.data["snapshots"][snapshot_id]

    def delete_snapshot(self, snapshot_id: str) -> dict:
        snapshot = self.get_snapshot(snapshot_id)
        del self.data["snapshots"][snapshot_id]
        self._save()
        return snapshot

    def update_file(
        self,
        file_id: str,
        filename: str,
        original_path: str,
        size: int,
        chunking: str,
        chunks: List[str],
        relative_path: str | None = None,
        snapshot_id: str | None = None,
    ) -> dict:
        current = self.get_file(file_id)
        self.data["files"][file_id] = self._build_file_record(
            filename=filename,
            original_path=original_path,
            size=size,
            chunking=chunking,
            chunks=chunks,
            created_at=current.get("created_at"),
            relative_path=relative_path,
            snapshot_id=snapshot_id,
        )
        self._save()
        return self.data["files"][file_id]

    def delete_file(self, file_id: str) -> dict:
        file_meta = self.get_file(file_id)
        del self.data["files"][file_id]
        self._save()
        return file_meta

    def get_all_chunks(self) -> List[str]:
        """Return all chunk hashes referenced by stored files (for stats)."""
        chunks = []
        for meta in self.data["files"].values():
            chunks.extend(meta["chunks"])
        return chunks
