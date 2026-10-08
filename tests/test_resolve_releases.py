import unittest
from unittest.mock import patch

from tools.resolve_releases import ResolutionError, resolve


CONFIG = {
    "immortalwrt": {"version": "25.12.2"},
    "rolling": {
        "argon_repository": "theme/repo",
        "openclash_repository": "clash/repo",
        "nginx_ui_repository": "nginx-ui/repo",
        "kernel_repository": "kernel/repo",
        "kernel_release_tag": "kernel_stable",
        "kernel_series": "6.18",
    },
}


def fixture(path):
    if path.endswith("theme/repo/releases/latest"):
        return {
            "tag_name": "v2.4.6",
            "assets": [
                {"name": "luci-theme-argon-2.4.6-r1.apk", "browser_download_url": "https://example/theme", "digest": "sha256:a"},
                {"name": "luci-app-argon-config-2.4.6-r1.apk", "browser_download_url": "https://example/config", "digest": "sha256:b"},
                {"name": "luci-i18n-argon-config-zh-cn-26.1.abc.apk", "browser_download_url": "https://example/i18n", "digest": "sha256:c"},
            ],
        }
    if path.endswith("clash/repo/releases/latest"):
        return {
            "tag_name": "v0.47.156",
            "assets": [{"name": "luci-app-openclash-0.47.156.apk", "browser_download_url": "https://example/clash", "digest": "sha256:d"}],
        }
    if path.endswith("nginx-ui/repo/releases?per_page=20"):
        return [
            {
                "tag_name": "v2.5.7",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "nginx-ui-termux-arm64-v8a.tar.gz",
                        "browser_download_url": "https://example/nginx-ui-termux",
                    }
                ],
            },
            {
                "tag_name": "v2.5.6",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "nginx-ui-linux-arm64-v8a.tar.gz",
                        "browser_download_url": "https://example/nginx-ui",
                        "digest": "sha256:j",
                    }
                ],
            },
        ]
    return {
        "tag_name": "kernel_stable",
        "assets": [
            {"name": "6.12.99.tar.gz", "browser_download_url": "https://example/99", "digest": "sha256:e"},
            {"name": "6.12.102.tar.gz", "browser_download_url": "https://example/102", "digest": "sha256:f"},
            {"name": "6.18.1.tar.gz", "browser_download_url": "https://example/6181", "digest": "sha256:g"},
            {"name": "6.18.41.tar.gz", "browser_download_url": "https://example/61841", "digest": "sha256:h"},
        ],
    }


class ResolveReleaseTests(unittest.TestCase):
    @patch("tools.resolve_releases.github_json", side_effect=fixture)
    def test_selects_latest_patch_from_requested_kernel_series(self, _request):
        result = resolve(CONFIG)

        self.assertEqual("6.18.41.tar.gz", result["kernel"]["asset"]["name"])
        self.assertEqual("v2.4.6", result["argon"]["tag"])
        self.assertEqual("luci-app-openclash-0.47.156.apk", result["openclash"]["assets"][0]["name"])
        self.assertEqual(
            "nginx-ui-linux-arm64-v8a.tar.gz",
            result["nginx_ui"]["assets"][0]["name"],
        )
        self.assertEqual("v2.5.6", result["nginx_ui"]["tag"])

    @patch("tools.resolve_releases.github_json", side_effect=fixture)
    def test_uses_configured_kernel_version_by_default(self, _request):
        config = {**CONFIG, "rolling": {**CONFIG["rolling"], "kernel_version": "6.18.1"}}
        result = resolve(config)

        self.assertEqual("6.18.1.tar.gz", result["kernel"]["asset"]["name"])

    @patch("tools.resolve_releases.github_json", side_effect=fixture)
    def test_exact_kernel_override_is_honored(self, _request):
        result = resolve(CONFIG, "6.18.1")

        self.assertEqual("6.18.1.tar.gz", result["kernel"]["asset"]["name"])

    @patch("tools.resolve_releases.github_json", side_effect=fixture)
    def test_missing_exact_kernel_is_rejected(self, _request):
        with self.assertRaises(ResolutionError):
            resolve(CONFIG, "6.18.77")


if __name__ == "__main__":
    unittest.main()
