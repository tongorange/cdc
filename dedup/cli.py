import argparse
import sys
from pathlib import Path
from .filesystem import DedupFileSystem


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
    fs = DedupFileSystem(data_dir)
    return fs.create_file(
        input_file=input_file,
        chunking=chunking,
        chunk_size=chunk_size,
        min_size=min_size,
        avg_size=avg_size,
        max_size=max_size,
        window_size=window_size,
    )


def backup_path(input_path: Path, data_dir: Path, description: str | None = None, **chunking_options) -> dict:
    fs = DedupFileSystem(data_dir)
    return fs.backup_path(input_path, description=description, **chunking_options)


def restore_file(file_id: str, output_file: Path, data_dir: Path) -> dict:
    fs = DedupFileSystem(data_dir)
    return fs.restore_file(file_id, output_file)


def restore_snapshot(snapshot_id: str, output_dir: Path, data_dir: Path) -> dict:
    fs = DedupFileSystem(data_dir)
    return fs.restore_snapshot(snapshot_id, output_dir)


def list_files(data_dir: Path, filename: str | None = None) -> None:
    fs = DedupFileSystem(data_dir)
    files = fs.list_files(filename)
    if not files:
        print("No files stored.")
        return
    print(f"{'ID':<5} {'Filename':<30} {'Size':<12} {'Chunking':<8} {'Chunks':<8} {'Updated At'}")
    for fid, info in files.items():
        print(
            f"{fid:<5} {info['filename']:<30} {info['size']:<12} "
            f"{info['chunking']:<8} {len(info['chunks']):<8} {info.get('updated_at', '-')}"
        )


def list_snapshots(data_dir: Path) -> None:
    fs = DedupFileSystem(data_dir)
    snapshots = fs.list_snapshots()
    if not snapshots:
        print("No snapshots stored.")
        return
    print(f"{'ID':<5} {'Files':<8} {'Chunking':<8} {'Source Path'}")
    for snapshot_id, info in snapshots.items():
        print(f"{snapshot_id:<5} {info['file_count']:<8} {info['chunking']:<8} {info['source_path']}")


def info_file(file_id: str, data_dir: Path) -> None:
    fs = DedupFileSystem(data_dir)
    info = fs.read_file(file_id)
    print(f"ID: {file_id}")
    print(f"Filename: {info['filename']}")
    print(f"Original path: {info['original_path']}")
    print(f"Size: {info['size']} bytes")
    print(f"Chunking: {info['chunking']}")
    print(f"Chunk count: {len(info['chunks'])}")
    print(f"Created at: {info.get('created_at', '-')}")
    print(f"Updated at: {info.get('updated_at', '-')}")


def info_snapshot(snapshot_id: str, data_dir: Path) -> None:
    fs = DedupFileSystem(data_dir)
    info = fs.read_snapshot(snapshot_id)
    print(f"Snapshot ID: {snapshot_id}")
    print(f"Source path: {info['source_path']}")
    print(f"Chunking: {info['chunking']}")
    print(f"File count: {info['file_count']}")
    print(f"Created at: {info.get('created_at', '-')}")
    print(f"Updated at: {info.get('updated_at', '-')}")
    print(f"Description: {info.get('description') or '-'}")


def update_file(file_id: str, input_file: Path, data_dir: Path, **chunking_options) -> dict:
    fs = DedupFileSystem(data_dir)
    return fs.update_file(file_id, input_file, **chunking_options)


def delete_file(file_id: str, data_dir: Path) -> dict:
    fs = DedupFileSystem(data_dir)
    return fs.delete_file(file_id)


def delete_snapshot(snapshot_id: str, data_dir: Path) -> dict:
    fs = DedupFileSystem(data_dir)
    return fs.delete_snapshot(snapshot_id)


def stat_files(data_dir: Path) -> None:
    fs = DedupFileSystem(data_dir)
    stats = fs.stats()
    print(f"Snapshots: {stats['snapshot_count']}")
    print(f"Files: {stats['file_count']}")
    print(f"Logical size: {stats['logical_size']} bytes")
    print(f"Physical size: {stats['physical_size']} bytes")
    print(f"Total chunk refs: {stats['chunk_count_total']}")
    print(f"Unique chunks: {stats['chunk_count_unique']}")
    print(f"Duplicate chunk refs: {stats['duplicate_chunk_refs']}")
    print(f"Stored chunks: {stats['stored_chunk_count']}")
    print(f"Orphan chunks: {stats['orphan_chunk_count']}")
    print(f"Saving ratio: {stats['saving_ratio']:.2%}")

def main():
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Data directory")

    parser = argparse.ArgumentParser(description="Deduplication CLI", parents=[parent_parser])
    subparsers = parser.add_subparsers(dest="command", required=True)

    store_parser = subparsers.add_parser("store", parents=[parent_parser])
    store_parser.add_argument("input_file", type=Path)
    store_parser.add_argument("--chunking", choices=["fixed", "cdc"], default="fixed")
    store_parser.add_argument("--chunk-size", type=int, default=4096, help="Fixed chunk size")
    store_parser.add_argument("--min-size", type=int, default=2048)
    store_parser.add_argument("--avg-size", type=int, default=4096)
    store_parser.add_argument("--max-size", type=int, default=8192)
    store_parser.add_argument("--window-size", type=int, default=48)

    backup_parser = subparsers.add_parser("backup", parents=[parent_parser])
    backup_parser.add_argument("input_path", type=Path)
    backup_parser.add_argument("--description", type=str, default=None)
    backup_parser.add_argument("--chunking", choices=["fixed", "cdc"], default="fixed")
    backup_parser.add_argument("--chunk-size", type=int, default=4096, help="Fixed chunk size")
    backup_parser.add_argument("--min-size", type=int, default=2048)
    backup_parser.add_argument("--avg-size", type=int, default=4096)
    backup_parser.add_argument("--max-size", type=int, default=8192)
    backup_parser.add_argument("--window-size", type=int, default=48)

    restore_parser = subparsers.add_parser("restore", parents=[parent_parser])
    restore_parser.add_argument("target_id", type=str)
    restore_parser.add_argument("output_path", type=Path)
    restore_parser.add_argument("--kind", choices=["auto", "file", "snapshot"], default="auto")

    list_parser = subparsers.add_parser("list", parents=[parent_parser])
    list_parser.add_argument("--filename", type=str, default=None, help="Filter by exact filename")

    subparsers.add_parser("list-snapshots", parents=[parent_parser])

    info_parser = subparsers.add_parser("info", parents=[parent_parser])
    info_parser.add_argument("target_id", type=str)
    info_parser.add_argument("--kind", choices=["auto", "file", "snapshot"], default="auto")

    update_parser = subparsers.add_parser("update", parents=[parent_parser])
    update_parser.add_argument("file_id", type=str)
    update_parser.add_argument("input_file", type=Path)
    update_parser.add_argument("--chunking", choices=["fixed", "cdc"], default="fixed")
    update_parser.add_argument("--chunk-size", type=int, default=4096, help="Fixed chunk size")
    update_parser.add_argument("--min-size", type=int, default=2048)
    update_parser.add_argument("--avg-size", type=int, default=4096)
    update_parser.add_argument("--max-size", type=int, default=8192)
    update_parser.add_argument("--window-size", type=int, default=48)

    delete_parser = subparsers.add_parser("delete", parents=[parent_parser])
    delete_parser.add_argument("target_id", type=str)
    delete_parser.add_argument("--kind", choices=["auto", "file", "snapshot"], default="auto")

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
        elif args.command == "backup":
            result = backup_path(
                args.input_path,
                data_dir,
                description=args.description,
                chunking=args.chunking,
                chunk_size=args.chunk_size,
                min_size=args.min_size,
                avg_size=args.avg_size,
                max_size=args.max_size,
                window_size=args.window_size,
            )
            if result["kind"] == "snapshot":
                print(f"Stored snapshot with ID: {result['snapshot_id']}")
                print(f"  Files: {result['file_count']}")
            else:
                print(f"Stored file with ID: {result['file_id']}")
            print(f"  Size: {result['size']} bytes")
            print(f"  Total chunks: {result['chunk_count']}")
            print(f"  New chunks: {result['new_chunk_count']}")
            print(f"  Duplicate chunks: {result['duplicate_chunk_count']}")
        elif args.command == "restore":
            fs = DedupFileSystem(data_dir)
            kind = args.kind
            if kind == "auto":
                kind = "snapshot" if args.target_id in fs.list_snapshots() else "file"
            if kind == "snapshot":
                result = restore_snapshot(args.target_id, args.output_path, data_dir)
                print(f"Restored snapshot {args.target_id} to {result['output_dir']} ({result['file_count']} files)")
            else:
                result = restore_file(args.target_id, args.output_path, data_dir)
                print(f"Restored file to {result['output_file']} ({result['size']} bytes)")
        elif args.command == "list":
            list_files(data_dir, args.filename)
        elif args.command == "list-snapshots":
            list_snapshots(data_dir)
        elif args.command == "info":
            fs = DedupFileSystem(data_dir)
            kind = args.kind
            if kind == "auto":
                kind = "snapshot" if args.target_id in fs.list_snapshots() else "file"
            if kind == "snapshot":
                info_snapshot(args.target_id, data_dir)
            else:
                info_file(args.target_id, data_dir)
        elif args.command == "update":
            result = update_file(
                args.file_id,
                args.input_file,
                data_dir,
                chunking=args.chunking,
                chunk_size=args.chunk_size,
                min_size=args.min_size,
                avg_size=args.avg_size,
                max_size=args.max_size,
                window_size=args.window_size,
            )
            print(f"Updated file ID: {result['file_id']}")
            print(f"  Previous size: {result['previous_size']} bytes")
            print(f"  New size: {result['size']} bytes")
            print(f"  Total chunks: {result['chunk_count']}")
            print(f"  New chunks: {result['new_chunk_count']}")
            print(f"  Duplicate chunks: {result['duplicate_chunk_count']}")
            print(f"  Reclaimed chunks: {result['reclaimed_chunk_count']}")
        elif args.command == "delete":
            fs = DedupFileSystem(data_dir)
            kind = args.kind
            if kind == "auto":
                kind = "snapshot" if args.target_id in fs.list_snapshots() else "file"
            if kind == "snapshot":
                result = delete_snapshot(args.target_id, data_dir)
                print(f"Deleted snapshot ID: {result['snapshot_id']} ({result['file_count']} files)")
            else:
                result = delete_file(args.target_id, data_dir)
                print(f"Deleted file ID: {result['file_id']} ({result['filename']}, {result['size']} bytes)")
            print(f"  Reclaimed chunks: {result['reclaimed_chunk_count']}")
        elif args.command == "stat":
            stat_files(data_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
