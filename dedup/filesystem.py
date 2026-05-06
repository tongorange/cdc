from pathlib import Path

from .chunker import cdc_chunk_file, fixed_chunk_file
from .hashing import sha256_bytes
from .metadata import MetadataStore
from .stats import collect_stats
from .storage import ChunkStore


class DedupFileSystem:
    """Minimal CRUD file system built on deduplicated chunk storage."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.meta = MetadataStore(self.data_dir)
        self.store = ChunkStore(self.data_dir)

    def create_file(
        self,
        input_file: Path,
        chunking: str = "fixed",
        chunk_size: int = 4096,
        min_size: int = 2048,
        avg_size: int = 4096,
        max_size: int = 8192,
        window_size: int = 48,
    ) -> dict:
        return self._ingest_file(
            input_file=input_file,
            chunking=chunking,
            chunk_size=chunk_size,
            min_size=min_size,
            avg_size=avg_size,
            max_size=max_size,
            window_size=window_size,
        )

    def _ingest_file(
        self,
        input_file: Path,
        chunking: str = "fixed",
        chunk_size: int = 4096,
        min_size: int = 2048,
        avg_size: int = 4096,
        max_size: int = 8192,
        window_size: int = 48,
        relative_path: str | None = None,
        snapshot_id: str | None = None,
    ) -> dict:
        input_path = Path(input_file)
        if not input_path.is_file():
            raise FileNotFoundError(f"File not found: {input_path}")

        if chunking == "fixed":
            chunks_iter = fixed_chunk_file(input_path, chunk_size)
        elif chunking == "cdc":
            chunks_iter = cdc_chunk_file(input_path, min_size, avg_size, max_size, window_size)
        else:
            raise ValueError("chunking must be 'fixed' or 'cdc'")

        chunk_hashes = []
        new_count = 0
        dup_count = 0
        for chunk in chunks_iter:
            chunk_hash = sha256_bytes(chunk)
            chunk_hashes.append(chunk_hash)
            if self.store.put_chunk(chunk_hash, chunk):
                new_count += 1
            else:
                dup_count += 1

        file_size = input_path.stat().st_size
        file_id = self.meta.add_file(
            filename=input_path.name,
            original_path=str(input_path.absolute()),
            size=file_size,
            chunking=chunking,
            chunks=chunk_hashes,
            relative_path=relative_path,
            snapshot_id=snapshot_id,
        )
        return {
            "file_id": file_id,
            "filename": input_path.name,
            "size": file_size,
            "chunking": chunking,
            "chunk_count": len(chunk_hashes),
            "new_chunk_count": new_count,
            "duplicate_chunk_count": dup_count,
            "relative_path": relative_path,
            "snapshot_id": snapshot_id,
        }

    def backup_path(self, input_path: Path, description: str | None = None, **chunking_options) -> dict:
        source_path = Path(input_path)
        if source_path.is_file():
            file_result = self.create_file(source_path, **chunking_options)
            file_result["kind"] = "file"
            return file_result
        if not source_path.is_dir():
            raise FileNotFoundError(f"Path not found: {source_path}")

        file_ids = []
        total_size = 0
        total_new = 0
        total_dup = 0
        total_chunks = 0
        chunking = chunking_options.get("chunking", "fixed")
        for file_path in sorted(p for p in source_path.rglob("*") if p.is_file()):
            relative_path = str(file_path.relative_to(source_path))
            result = self._ingest_file(
                file_path,
                relative_path=relative_path,
                **chunking_options,
            )
            file_ids.append(result["file_id"])
            total_size += result["size"]
            total_new += result["new_chunk_count"]
            total_dup += result["duplicate_chunk_count"]
            total_chunks += result["chunk_count"]

        snapshot_id = self.meta.add_snapshot(
            source_path=str(source_path.absolute()),
            chunking=chunking,
            file_ids=file_ids,
            file_count=len(file_ids),
            description=description,
        )
        for file_id in file_ids:
            file_meta = self.meta.get_file(file_id)
            self.meta.update_file(
                file_id=file_id,
                filename=file_meta["filename"],
                original_path=file_meta["original_path"],
                size=file_meta["size"],
                chunking=file_meta["chunking"],
                chunks=file_meta["chunks"],
                relative_path=file_meta.get("relative_path"),
                snapshot_id=snapshot_id,
            )

        return {
            "kind": "snapshot",
            "snapshot_id": snapshot_id,
            "source_path": str(source_path),
            "file_count": len(file_ids),
            "size": total_size,
            "chunk_count": total_chunks,
            "new_chunk_count": total_new,
            "duplicate_chunk_count": total_dup,
            "chunking": chunking,
        }

    def read_file(self, file_id: str) -> dict:
        return self.meta.get_file(file_id)

    def read_snapshot(self, snapshot_id: str) -> dict:
        return self.meta.get_snapshot(snapshot_id)

    def list_files(self, filename: str | None = None) -> dict[str, dict]:
        if filename is None:
            return self.meta.list_files()
        return self.meta.find_files_by_name(filename)

    def list_snapshots(self) -> dict[str, dict]:
        return self.meta.list_snapshots()

    def restore_file(self, file_id: str, output_file: Path) -> dict:
        file_meta = self.meta.get_file(file_id)
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as out:
            for chunk_hash in file_meta["chunks"]:
                out.write(self.store.get_chunk(chunk_hash))
        return {
            "file_id": file_id,
            "output_file": str(output_path),
            "size": file_meta["size"],
        }

    def restore_snapshot(self, snapshot_id: str, output_dir: Path) -> dict:
        snapshot = self.meta.get_snapshot(snapshot_id)
        restored_count = 0
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        for file_id in snapshot["file_ids"]:
            file_meta = self.meta.get_file(file_id)
            relative_path = file_meta.get("relative_path") or file_meta["filename"]
            self.restore_file(file_id, output_root / relative_path)
            restored_count += 1
        return {
            "snapshot_id": snapshot_id,
            "output_dir": str(output_root),
            "file_count": restored_count,
        }

    def update_file(self, file_id: str, input_file: Path, **chunking_options) -> dict:
        old_meta = self.meta.get_file(file_id)
        result = self._ingest_file(
            input_file=input_file,
            **chunking_options,
            relative_path=old_meta.get("relative_path"),
            snapshot_id=old_meta.get("snapshot_id"),
        )
        new_meta = self.meta.get_file(result["file_id"])
        self.meta.delete_file(result["file_id"])
        self.meta.update_file(
            file_id=file_id,
            filename=new_meta["filename"],
            original_path=new_meta["original_path"],
            size=new_meta["size"],
            chunking=new_meta["chunking"],
            chunks=new_meta["chunks"],
            relative_path=new_meta.get("relative_path"),
            snapshot_id=new_meta.get("snapshot_id"),
        )
        reclaimed_chunks = self.garbage_collect()
        result["file_id"] = file_id
        result["reclaimed_chunk_count"] = reclaimed_chunks
        result["previous_size"] = old_meta["size"]
        return result

    def delete_file(self, file_id: str) -> dict:
        deleted = self.meta.delete_file(file_id)
        snapshot_id = deleted.get("snapshot_id")
        if snapshot_id and snapshot_id in self.meta.list_snapshots():
            snapshot = self.meta.get_snapshot(snapshot_id)
            remaining_file_ids = [fid for fid in snapshot["file_ids"] if fid != file_id]
            if remaining_file_ids:
                self.meta.update_snapshot(
                    snapshot_id=snapshot_id,
                    source_path=snapshot["source_path"],
                    chunking=snapshot["chunking"],
                    file_ids=remaining_file_ids,
                    file_count=len(remaining_file_ids),
                    description=snapshot.get("description"),
                )
            else:
                self.meta.delete_snapshot(snapshot_id)
        reclaimed_chunks = self.garbage_collect()
        return {
            "file_id": file_id,
            "filename": deleted["filename"],
            "size": deleted["size"],
            "reclaimed_chunk_count": reclaimed_chunks,
        }

    def delete_snapshot(self, snapshot_id: str) -> dict:
        snapshot = self.meta.get_snapshot(snapshot_id)
        reclaimed = 0
        for file_id in list(snapshot["file_ids"]):
            result = self.delete_file(file_id)
            reclaimed += result["reclaimed_chunk_count"]
        if snapshot_id in self.meta.list_snapshots():
            self.meta.delete_snapshot(snapshot_id)
        return {
            "snapshot_id": snapshot_id,
            "file_count": snapshot["file_count"],
            "reclaimed_chunk_count": reclaimed,
        }

    def garbage_collect(self) -> int:
        referenced = set(self.meta.get_all_chunks())
        removed = 0
        for chunk_hash in self.store.list_chunk_hashes():
            if chunk_hash not in referenced and self.store.delete_chunk(chunk_hash):
                removed += 1
        return removed

    def stats(self) -> dict:
        return collect_stats(self.data_dir)
