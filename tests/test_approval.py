import tempfile
import unittest
from pathlib import Path

from atlas_dev.approval import target_file, digest


class TestApprovalSafety(unittest.TestCase):
    def test_hash_is_deterministic(self):
        self.assertEqual(digest("hello"), digest("hello"))

    def test_hash_detects_changes(self):
        self.assertNotEqual(digest("before"), digest("after"))

    def test_valid_python_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "example.py"
            path.write_text("x = 1\n")
            self.assertEqual(target_file(tmp, "example.py"), path)

    def test_reject_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            root.mkdir()
            outside = Path(tmp) / "outside.py"
            outside.write_text("x = 1\n")

            with self.assertRaises(ValueError):
                target_file(root, "../outside.py")

    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real.py"
            real.write_text("x = 1\n")
            (root / "link.py").symlink_to(real)

            with self.assertRaises(ValueError):
                target_file(root, "link.py")


if __name__ == "__main__":
    unittest.main()
