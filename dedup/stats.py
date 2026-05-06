from pathlib import Path
from .storage import ChunkStore
from .metadata import MetadataStore

def collect_stats(data_dir: Path) -> dict:
    """Compute dedup statistics."""
    meta = MetadataStore(data_dir)
    store = ChunkStore(data_dir)

    files_meta = meta.list_files()
    snapshots_meta = meta.list_snapshots()
    file_count = len(files_meta)
    snapshot_count = len(snapshots_meta)
    logical_size = sum(m["size"] for m in files_meta.values())
    chunk_refs = meta.get_all_chunks()
    total_chunk_refs = len(chunk_refs)
    unique_chunks = set(chunk_refs)
    unique_count = len(unique_chunks)
    duplicate_refs = total_chunk_refs - unique_count

    physical_size = 0
    for h in unique_chunks:
        try:
            physical_size += store.get_chunk_size(h)
        except FileNotFoundError:
            # 一致性错误，忽略
            pass

    stored_chunks = set(store.list_chunk_hashes())
    orphan_chunks = stored_chunks - unique_chunks

    saving_ratio = 0.0
    if logical_size > 0:
        saving_ratio = 1 - physical_size / logical_size

    # 分块方法统计
    chunking_methods = {"fixed": 0, "cdc": 0}
    for m in files_meta.values():
        chunking_methods[m["chunking"]] += 1

    return {
        "file_count": file_count,
        "snapshot_count": snapshot_count,
        "logical_size": logical_size,
        "physical_size": physical_size,
        "chunk_count_total": total_chunk_refs,
        "chunk_count_unique": unique_count,
        "duplicate_chunk_refs": duplicate_refs,
        "stored_chunk_count": len(stored_chunks),
        "orphan_chunk_count": len(orphan_chunks),
        "saving_ratio": saving_ratio,
        "chunking_methods": chunking_methods,
    }
