import unittest
from pathlib import PurePosixPath

from tools.archive_paths import safe_member_path


class ArchivePathTests(unittest.TestCase):
    def test_accepts_relative_archive_path(self):
        self.assertEqual(safe_member_path("boot/Image"), PurePosixPath("boot/Image"))

    def test_rejects_absolute_archive_path(self):
        with self.assertRaisesRegex(ValueError, "unsafe archive member"):
            safe_member_path("/etc/passwd")

    def test_rejects_parent_traversal(self):
        with self.assertRaisesRegex(ValueError, "unsafe archive member"):
            safe_member_path("boot/../../outside")


if __name__ == "__main__":
    unittest.main()
