import tempfile
import unittest
from pathlib import Path

from dedup.chunker import cdc_chunk_file, fixed_chunk_file
from dedup.filesystem import DedupFileSystem


class DedupFileSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.input_dir = self.root / "inputs"
        self.input_dir.mkdir()
        self.fs = DedupFileSystem(self.data_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_input(self, name: str, data: bytes) -> Path:
        path = self.input_dir / name
        path.write_bytes(data)
        return path

    def test_create_and_restore_file(self):
        source = self._write_input("alpha.bin", bytes(range(256)))
        result = self.fs.create_file(source, chunking="fixed", chunk_size=16)

        restored = self.root / "restored.bin"
        self.fs.restore_file(result["file_id"], restored)

        self.assertEqual(restored.read_bytes(), source.read_bytes())
        self.assertEqual(result["new_chunk_count"], result["chunk_count"])

    def test_delete_reclaims_unreferenced_chunks(self):
        shared = (b"ABCD" * 64) + (b"TAIL" * 8)
        source_a = self._write_input("a.bin", shared)
        source_b = self._write_input("b.bin", shared)

        file_a = self.fs.create_file(source_a, chunking="fixed", chunk_size=32)
        file_b = self.fs.create_file(source_b, chunking="fixed", chunk_size=32)
        stats_before = self.fs.stats()
        delete_a = self.fs.delete_file(file_a["file_id"])
        stats_mid = self.fs.stats()
        delete_b = self.fs.delete_file(file_b["file_id"])
        stats_after = self.fs.stats()

        self.assertEqual(delete_a["reclaimed_chunk_count"], 0)
        self.assertGreaterEqual(stats_before["chunk_count_unique"], 1)
        self.assertGreater(delete_b["reclaimed_chunk_count"], 0)
        self.assertEqual(stats_mid["file_count"], 1)
        self.assertEqual(stats_after["stored_chunk_count"], 0)

    def test_update_rewrites_metadata_and_gc(self):
        original = self._write_input("doc.bin", b"A" * 128 + b"B" * 128)
        updated = self._write_input("doc_v2.bin", b"A" * 128 + b"C" * 128)
        created = self.fs.create_file(original, chunking="fixed", chunk_size=64)

        result = self.fs.update_file(created["file_id"], updated, chunking="fixed", chunk_size=64)
        restored = self.root / "updated_restore.bin"
        self.fs.restore_file(created["file_id"], restored)
        info = self.fs.read_file(created["file_id"])

        self.assertEqual(result["file_id"], created["file_id"])
        self.assertEqual(restored.read_bytes(), updated.read_bytes())
        self.assertEqual(info["filename"], "doc_v2.bin")
        self.assertEqual(info["size"], len(updated.read_bytes()))

    def test_list_by_filename(self):
        a1 = self._write_input("same.bin", b"A" * 80)
        a2 = self._write_input("same2.bin", b"B" * 80)
        self.fs.create_file(a1)
        self.fs.create_file(a2)

        results = self.fs.list_files("same.bin")
        self.assertEqual(len(results), 1)
        only_meta = next(iter(results.values()))
        self.assertEqual(only_meta["filename"], "same.bin")

    def test_backup_and_restore_directory_snapshot(self):
        source_dir = self.root / "dataset"
        (source_dir / "sub").mkdir(parents=True)
        (source_dir / "a.bin").write_bytes(b"A" * 64)
        (source_dir / "sub" / "b.bin").write_bytes(b"B" * 64)

        result = self.fs.backup_path(source_dir, chunking="fixed", chunk_size=16)
        restored_dir = self.root / "restored_dataset"
        restore = self.fs.restore_snapshot(result["snapshot_id"], restored_dir)
        snapshot = self.fs.read_snapshot(result["snapshot_id"])

        self.assertEqual(result["kind"], "snapshot")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(restore["file_count"], 2)
        self.assertEqual(snapshot["file_count"], 2)
        self.assertEqual((restored_dir / "a.bin").read_bytes(), (source_dir / "a.bin").read_bytes())
        self.assertEqual((restored_dir / "sub" / "b.bin").read_bytes(), (source_dir / "sub" / "b.bin").read_bytes())


class ChunkerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fixed_chunker(self):
        path = self.root / "fixed.bin"
        path.write_bytes(b"0123456789")
        chunks = list(fixed_chunk_file(path, chunk_size=4))
        self.assertEqual(chunks, [b"0123", b"4567", b"89"])

    def test_cdc_fallback_chunks_cover_full_file(self):
        path = self.root / "cdc.bin"
        path.write_bytes((b"ABCD" * 128) + (b"XYZ" * 64))
        chunks = list(cdc_chunk_file(path, min_size=32, avg_size=64, max_size=128, window_size=8))

        self.assertTrue(chunks)
        self.assertEqual(b"".join(chunks), path.read_bytes())
        self.assertTrue(all(0 < len(chunk) <= 128 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
