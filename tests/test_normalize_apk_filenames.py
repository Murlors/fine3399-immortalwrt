import unittest

from tools.normalize_apk_filenames import package_identity


class NormalizeApkFilenamesTests(unittest.TestCase):
    def test_reads_canonical_identity_from_apk_metadata(self):
        self.assertEqual(
            package_identity(
                {"packages": [{"name": "luci-i18n-argon-config-zh-cn", "version": "26.281.11209~9bafffa"}]}
            ),
            ("luci-i18n-argon-config-zh-cn", "26.281.11209~9bafffa"),
        )

    def test_reads_single_package_adbdump_object(self):
        self.assertEqual(
            package_identity({"name": "luci-theme-argon", "version": "2.4.8-r1"}),
            ("luci-theme-argon", "2.4.8-r1"),
        )

    def test_reads_package_identity_from_adbdump_info(self):
        self.assertEqual(
            package_identity(
                {
                    "info": {"name": "luci-theme-argon", "version": "2.4.8-r1"},
                    "paths": [{"name": "usr/share/luci"}],
                }
            ),
            ("luci-theme-argon", "2.4.8-r1"),
        )

    def test_rejects_multiple_package_records(self):
        with self.assertRaisesRegex(ValueError, "exactly one package"):
            package_identity({"packages": [{"name": "first", "version": "1"}, {"name": "second", "version": "2"}]})

    def test_accepts_unusual_but_filename_safe_identity_characters(self):
        self.assertEqual(
            package_identity(
                {"info": {"name": "custom package+variant", "version": "v2-preview~1+build"}}
            ),
            ("custom package+variant", "v2-preview~1+build"),
        )

    def test_rejects_path_separators_in_package_identity(self):
        with self.assertRaisesRegex(ValueError, "invalid APK package name"):
            package_identity({"packages": [{"name": "../escape", "version": "1"}]})

    def test_rejects_control_characters_in_package_identity(self):
        with self.assertRaisesRegex(ValueError, "invalid APK package version"):
            package_identity({"info": {"name": "safe-name", "version": "1\n2"}})


if __name__ == "__main__":
    unittest.main()
