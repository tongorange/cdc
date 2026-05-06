import csv
import hashlib
import shutil
import time
from pathlib import Path

from .filesystem import DedupFileSystem


FIXED_PARAMS = {"chunking": "fixed", "chunk_size": 8192}
CDC_PARAMS = {"chunking": "cdc", "min_size": 2048, "avg_size": 8192, "max_size": 16384, "window_size": 48}
CDC_PARAMETER_PROFILES = {
    "cdc_4k": {"chunking": "cdc", "min_size": 1024, "avg_size": 4096, "max_size": 8192, "window_size": 48},
    "cdc_8k": {"chunking": "cdc", "min_size": 2048, "avg_size": 8192, "max_size": 16384, "window_size": 48},
    "cdc_16k": {"chunking": "cdc", "min_size": 4096, "avg_size": 16384, "max_size": 32768, "window_size": 48},
    "cdc_32k": {"chunking": "cdc", "min_size": 8192, "avg_size": 32768, "max_size": 65536, "window_size": 48},
}
SCENARIOS = {
    "A_no_duplicate": "无重复数据集",
    "B_full_duplicate": "完全重复数据集",
    "C_local_modify": "局部修改数据集",
    "D_prefix_insert": "头部插入数据集",
    "E_delete_shift": "删除偏移数据集",
}
SCALE_DATASETS = {
    "size_10mb": 10,
    "size_50mb": 50,
    "size_100mb": 100,
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_directory_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha256_file(path)
        for path in sorted(p for p in root.rglob("*") if p.is_file())
    }


def compare_directories(left: Path, right: Path) -> bool:
    return collect_directory_hashes(left) == collect_directory_hashes(right)


def iter_methods():
    return [("fixed", FIXED_PARAMS), ("cdc", CDC_PARAMS)]


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def run_correctness_experiment(dataset_root: Path, results_dir: Path, repeats: int = 1) -> Path:
    rows = []
    for dataset_name in SCENARIOS:
        dataset_path = dataset_root / "scenarios" / dataset_name
        for method_name, params in iter_methods():
            for run_index in range(1, repeats + 1):
                store_dir = results_dir / "stores" / "correctness" / f"{dataset_name}_{method_name}_{run_index}"
                restore_dir = results_dir / "restored" / "correctness" / f"{dataset_name}_{method_name}_{run_index}"
                if store_dir.exists():
                    shutil.rmtree(store_dir)
                if restore_dir.exists():
                    shutil.rmtree(restore_dir)

                fs = DedupFileSystem(store_dir)
                backup_result = fs.backup_path(dataset_path, description=f"{dataset_name}:{method_name}", **params)
                restore_start = time.perf_counter()
                fs.restore_snapshot(backup_result["snapshot_id"], restore_dir)
                restore_time = time.perf_counter() - restore_start
                is_equal = compare_directories(dataset_path, restore_dir)
                rows.append([
                    dataset_name,
                    method_name,
                    run_index,
                    backup_result["file_count"],
                    "yes",
                    "yes",
                    "yes" if is_equal else "no",
                    round(restore_time, 6),
                ])

    output = results_dir / "correctness_results.csv"
    write_csv(
        output,
        ["dataset", "method", "run_index", "file_count", "backup_ok", "metadata_ok", "restore_hash_match", "restore_time_sec"],
        rows,
    )
    return output


def run_scenario_comparison(dataset_root: Path, results_dir: Path, repeats: int = 3) -> Path:
    rows = []
    for dataset_name in SCENARIOS:
        dataset_path = dataset_root / "scenarios" / dataset_name
        source_hashes = collect_directory_hashes(dataset_path)
        logical_size = sum((dataset_path / relative).stat().st_size for relative in source_hashes)
        for method_name, params in iter_methods():
            backup_times = []
            restore_times = []
            final_stats = None
            final_hash_ok = False
            for run_index in range(1, repeats + 1):
                store_dir = results_dir / "stores" / "scenario" / f"{dataset_name}_{method_name}_{run_index}"
                restore_dir = results_dir / "restored" / "scenario" / f"{dataset_name}_{method_name}_{run_index}"
                if store_dir.exists():
                    shutil.rmtree(store_dir)
                if restore_dir.exists():
                    shutil.rmtree(restore_dir)

                fs = DedupFileSystem(store_dir)
                backup_start = time.perf_counter()
                backup_result = fs.backup_path(dataset_path, description=f"{dataset_name}:{method_name}", **params)
                backup_times.append(time.perf_counter() - backup_start)
                restore_start = time.perf_counter()
                fs.restore_snapshot(backup_result["snapshot_id"], restore_dir)
                restore_times.append(time.perf_counter() - restore_start)
                final_stats = fs.stats()
                final_hash_ok = compare_directories(dataset_path, restore_dir)

            assert final_stats is not None
            dedup_ratio = (final_stats["logical_size"] / final_stats["physical_size"]) if final_stats["physical_size"] else 0.0
            rows.append([
                dataset_name,
                method_name,
                logical_size,
                final_stats["physical_size"],
                final_stats["chunk_count_total"],
                final_stats["chunk_count_unique"],
                final_stats["duplicate_chunk_refs"],
                round(dedup_ratio, 4),
                round(final_stats["saving_ratio"], 4),
                round(sum(backup_times) / len(backup_times), 6),
                round(sum(restore_times) / len(restore_times), 6),
                "yes" if final_hash_ok else "no",
            ])

    output = results_dir / "scenario_results.csv"
    write_csv(
        output,
        [
            "dataset",
            "method",
            "logical_size",
            "physical_size",
            "chunk_count_total",
            "chunk_count_unique",
            "duplicate_chunk_refs",
            "dedup_ratio",
            "saving_ratio",
            "backup_time_avg_sec",
            "restore_time_avg_sec",
            "restore_hash_match",
        ],
        rows,
    )
    return output


def run_cdc_parameter_experiment(dataset_root: Path, results_dir: Path, repeats: int = 3) -> Path:
    rows = []
    for dataset_name in ("D_prefix_insert", "E_delete_shift"):
        dataset_path = dataset_root / "scenarios" / dataset_name
        logical_size = sum(path.stat().st_size for path in dataset_path.rglob("*") if path.is_file())
        for profile_name, params in CDC_PARAMETER_PROFILES.items():
            backup_times = []
            restore_time = 0.0
            final_stats = None
            for run_index in range(1, repeats + 1):
                store_dir = results_dir / "stores" / "cdc_params" / f"{dataset_name}_{profile_name}_{run_index}"
                restore_dir = results_dir / "restored" / "cdc_params" / f"{dataset_name}_{profile_name}_{run_index}"
                if store_dir.exists():
                    shutil.rmtree(store_dir)
                if restore_dir.exists():
                    shutil.rmtree(restore_dir)

                fs = DedupFileSystem(store_dir)
                backup_start = time.perf_counter()
                backup_result = fs.backup_path(dataset_path, description=f"{dataset_name}:{profile_name}", **params)
                backup_times.append(time.perf_counter() - backup_start)
                restore_start = time.perf_counter()
                fs.restore_snapshot(backup_result["snapshot_id"], restore_dir)
                restore_time = time.perf_counter() - restore_start
                final_stats = fs.stats()

            assert final_stats is not None
            avg_chunk_size = final_stats["logical_size"] / final_stats["chunk_count_total"] if final_stats["chunk_count_total"] else 0.0
            dedup_ratio = (final_stats["logical_size"] / final_stats["physical_size"]) if final_stats["physical_size"] else 0.0
            rows.append([
                dataset_name,
                profile_name,
                logical_size,
                final_stats["chunk_count_total"],
                final_stats["chunk_count_unique"],
                round(avg_chunk_size, 2),
                round(dedup_ratio, 4),
                round(final_stats["saving_ratio"], 4),
                round(sum(backup_times) / len(backup_times), 6),
                round(restore_time, 6),
            ])

    output = results_dir / "cdc_parameter_results.csv"
    write_csv(
        output,
        [
            "dataset",
            "cdc_profile",
            "logical_size",
            "chunk_count_total",
            "chunk_count_unique",
            "avg_chunk_size",
            "dedup_ratio",
            "saving_ratio",
            "backup_time_avg_sec",
            "restore_time_sec",
        ],
        rows,
    )
    return output


def run_scale_experiment(dataset_root: Path, results_dir: Path, repeats: int = 3) -> Path:
    rows = []
    for scale_name, size_mb in SCALE_DATASETS.items():
        dataset_path = dataset_root / "scales" / scale_name
        logical_size = sum(path.stat().st_size for path in dataset_path.rglob("*") if path.is_file())
        logical_mb = logical_size / (1024 * 1024)
        for method_name, params in iter_methods():
            backup_times = []
            restore_times = []
            final_stats = None
            for run_index in range(1, repeats + 1):
                store_dir = results_dir / "stores" / "scale" / f"{scale_name}_{method_name}_{run_index}"
                restore_dir = results_dir / "restored" / "scale" / f"{scale_name}_{method_name}_{run_index}"
                if store_dir.exists():
                    shutil.rmtree(store_dir)
                if restore_dir.exists():
                    shutil.rmtree(restore_dir)

                fs = DedupFileSystem(store_dir)
                backup_start = time.perf_counter()
                backup_result = fs.backup_path(dataset_path, description=f"{scale_name}:{method_name}", **params)
                backup_times.append(time.perf_counter() - backup_start)
                restore_start = time.perf_counter()
                fs.restore_snapshot(backup_result["snapshot_id"], restore_dir)
                restore_times.append(time.perf_counter() - restore_start)
                final_stats = fs.stats()

            assert final_stats is not None
            avg_backup = sum(backup_times) / len(backup_times)
            dedup_ratio = (final_stats["logical_size"] / final_stats["physical_size"]) if final_stats["physical_size"] else 0.0
            rows.append([
                size_mb,
                method_name,
                round(avg_backup, 6),
                round(sum(restore_times) / len(restore_times), 6),
                final_stats["chunk_count_total"],
                round(logical_mb / avg_backup, 4) if avg_backup else 0.0,
                round(dedup_ratio, 4),
                round(final_stats["saving_ratio"], 4),
            ])

    output = results_dir / "scale_results.csv"
    write_csv(
        output,
        ["size_mb", "method", "backup_time_avg_sec", "restore_time_avg_sec", "chunk_count_total", "throughput_mb_per_sec", "dedup_ratio", "saving_ratio"],
        rows,
    )
    return output
