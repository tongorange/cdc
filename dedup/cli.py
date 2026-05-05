import argparse
import sys
from pathlib import Path
from .chunker import fixed_chunk_file, cdc_chunk_file
from .hashing import sha256_bytes
from .storage import ChunkStore
from .metadata import MetadataStore
from .stats import collect_stats

def store_file(
    input_file: Path,
    data_dir: Path,
    chunking: str = "fixed",
    chunk_size: int = 4096,
    min_size: int = 2048,
    avg_size: int = 4096,
    max_size: int = 8192,
    window_size: int = 48,
) -> dict:
    input_file = Path(input_file)
    if not input_file.is_file():
        raise FileNotFoundError(f"File not found: {input_file}")

    meta = MetadataStore(data_dir)
    store = ChunkStore(data_dir)

    if chunking == "fixed":
        chunks_iter = fixed_chunk_file(input_file, chunk_size)
    elif chunking == "cdc":
        chunks_iter = cdc_chunk_file(input_file, min_size, avg_size, max_size, window_size)
    else:
        raise ValueError("chunking must be 'fixed' or 'cdc'")

    chunk_hashes = []
    new_count = 0
    dup_count = 0
    for chunk in chunks_iter:
        h = sha256_bytes(chunk)
        chunk_hashes.append(h)
        if store.put_chunk(h, chunk):
            new_count += 1
        else:
            dup_count += 1

    file_size = input_file.stat().st_size
    file_id = meta.add_file(
        filename=input_file.name,
        original_path=str(input_file.absolute()),
        size=file_size,
        chunking=chunking,
        chunks=chunk_hashes,
    )

    return {
        "file_id": file_id,
        "filename": input_file.name,
        "size": file_size,
        "chunking": chunking,
        "chunk_count": len(chunk_hashes),
        "new_chunk_count": new_count,
        "duplicate_chunk_count": dup_count,
    }

def restore_file(file_id: str, output_file: Path, data_dir: Path) -> dict:
    meta = MetadataStore(data_dir)
    store = ChunkStore(data_dir)
    file_meta = meta.get_file(file_id)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as out:
        for h in file_meta["chunks"]:
            out.write(store.get_chunk(h))
    return {
        "file_id": file_id,
        "output_file": str(output_path),
        "size": file_meta["size"],
    }

def list_files(data_dir: Path) -> None:
    meta = MetadataStore(data_dir)
    files = meta.list_files()
    if not files:
        print("No files stored.")
        return
    print(f"{'ID':<5} {'Filename':<30} {'Size':<12} {'Chunking':<8} {'Chunks'}")
    for fid, info in files.items():
        print(f"{fid:<5} {info['filename']:<30} {info['size']:<12} {info['chunking']:<8} {len(info['chunks'])}")

def stat_files(data_dir: Path) -> None:
    stats = collect_stats(data_dir)
    print(f"Files: {stats['file_count']}")
    print(f"Logical size: {stats['logical_size']} bytes")
    print(f"Physical size: {stats['physical_size']} bytes")
    print(f"Total chunk refs: {stats['chunk_count_total']}")
    print(f"Unique chunks: {stats['chunk_count_unique']}")
    print(f"Duplicate chunk refs: {stats['duplicate_chunk_refs']}")
    print(f"Saving ratio: {stats['saving_ratio']:.2%}")

def main():
    # 父解析器，包含公共的 --data-dir 参数
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Data directory")

    parser = argparse.ArgumentParser(description="Deduplication CLI", parents=[parent_parser])
    subparsers = parser.add_subparsers(dest="command", required=True)

    # store 子命令
    store_parser = subparsers.add_parser("store", parents=[parent_parser])
    store_parser.add_argument("input_file", type=Path)
    store_parser.add_argument("--chunking", choices=["fixed", "cdc"], default="fixed")
    store_parser.add_argument("--chunk-size", type=int, default=4096, help="Fixed chunk size")
    store_parser.add_argument("--min-size", type=int, default=2048)
    store_parser.add_argument("--avg-size", type=int, default=4096)
    store_parser.add_argument("--max-size", type=int, default=8192)
    store_parser.add_argument("--window-size", type=int, default=48)

    # restore 子命令
    restore_parser = subparsers.add_parser("restore", parents=[parent_parser])
    restore_parser.add_argument("file_id", type=str)
    restore_parser.add_argument("output_file", type=Path)

    # list 子命令
    subparsers.add_parser("list", parents=[parent_parser])

    # stat 子命令
    subparsers.add_parser("stat", parents=[parent_parser])

    args = parser.parse_args()
    data_dir = args.data_dir

    try:
        if args.command == "store":
            result = store_file(
                args.input_file, data_dir,
                chunking=args.chunking,
                chunk_size=args.chunk_size,
                min_size=args.min_size,
                avg_size=args.avg_size,
                max_size=args.max_size,
                window_size=args.window_size,
            )
            print(f"Stored file with ID: {result['file_id']}")
            print(f"  Size: {result['size']} bytes")
            print(f"  Total chunks: {result['chunk_count']}")
            print(f"  New chunks: {result['new_chunk_count']}")
            print(f"  Duplicate chunks: {result['duplicate_chunk_count']}")
        elif args.command == "restore":
            result = restore_file(args.file_id, args.output_file, data_dir)
            print(f"Restored file to {result['output_file']} ({result['size']} bytes)")
        elif args.command == "list":
            list_files(data_dir)
        elif args.command == "stat":
            stat_files(data_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()