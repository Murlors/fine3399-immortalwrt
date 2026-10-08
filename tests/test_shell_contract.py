import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ShellContractTests(unittest.TestCase):
    def test_scripts_are_strict_and_do_not_leak_environment(self):
        for path in sorted((ROOT / "scripts").glob("*.sh")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("\r\n", path.read_bytes().decode("utf-8"), path)
            self.assertTrue(text.startswith("#!/usr/bin/env sh\nset -eu\n"), path)
            for forbidden in ("set -x", "curl |", "--force-depends", "env\n", "master", "main"):
                self.assertNotIn(forbidden, text, path)

    def test_committed_scripts_are_executable(self):
        for path in sorted((ROOT / "scripts").glob("*.sh")):
            result = subprocess.run(
                ["git", "ls-files", "--stage", "--", path.relative_to(ROOT).as_posix()],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            if result.stdout:
                self.assertTrue(result.stdout.startswith("100755 "), path)

    def test_pipeline_never_references_ophub_kernel_download_url(self):
        texts = "\n".join(path.read_text(encoding="utf-8") for path in [ROOT / "Makefile", *sorted((ROOT / "scripts").glob("*.sh"))])
        self.assertNotIn("ophub/kernel", texts)
        self.assertIn("FINE3399_KERNEL_BUNDLE", texts)

    def test_imagebuilder_local_apk_repository_uses_file_uri(self):
        script = (ROOT / "scripts/build-rootfs.sh").read_text(encoding="utf-8")

        self.assertIn("--repository file://$(PACKAGE_DIR)/packages.adb", script)
        self.assertIn("ImageBuilder local APK repository path is not supported.", script)
        self.assertIn("tools/normalize_apk_filenames.py", script)

    def test_workflow_verifies_before_upload(self):
        workflow = (ROOT / ".github/workflows/build-fine3399.yml").read_text(encoding="utf-8")
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("--privileged", workflow)
        self.assertLess(workflow.index("package-fine3399.sh"), workflow.index("actions/upload-artifact"))
        self.assertLess(workflow.index("verify_fast_artifacts.py"), workflow.index("actions/upload-artifact"))
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn('tags:\n      - "v*"', workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("actions/download-artifact", workflow)

    def test_release_excludes_intermediate_rootfs(self):
        package_script = (ROOT / "scripts/package-fine3399.sh").read_text(encoding="utf-8")

        self.assertIn('image_name="fine3399-immortalwrt-', package_script)
        self.assertNotIn('rootfs.tar.gz "$release_tmp', package_script)


if __name__ == "__main__": unittest.main()
