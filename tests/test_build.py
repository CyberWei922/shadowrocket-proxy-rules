from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402


OUTPUT = ROOT / "dist" / "sr_proxy_banad_custom.conf"


class GeneratedConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = OUTPUT.read_text(encoding="utf-8")
        cls.lines = cls.text.splitlines()

    def test_has_one_final_proxy(self) -> None:
        self.assertEqual(self.lines.count("FINAL,PROXY"), 1)

    def test_custom_rules_precede_final(self) -> None:
        begin = self.lines.index(build.RULES_BEGIN)
        end = self.lines.index(build.RULES_END)
        final = self.lines.index("FINAL,PROXY")
        self.assertLess(begin, end)
        self.assertLess(end, final)

    def test_upstream_ad_rules_precede_direct_rules(self) -> None:
        first_reject = next(
            index for index, line in enumerate(self.lines) if line.endswith(",REJECT")
        )
        custom_begin = self.lines.index(build.RULES_BEGIN)
        self.assertLess(first_reject, custom_begin)
        self.assertGreater(
            sum(line.endswith(",REJECT") for line in self.lines),
            50_000,
        )

    def test_required_direct_rules(self) -> None:
        required = {
            "DOMAIN-SUFFIX,push.apple.com,DIRECT",
            "DOMAIN-SUFFIX,weixin.qq.com,DIRECT",
            "DOMAIN-SUFFIX,qq.com,DIRECT",
            "DOMAIN-SUFFIX,bilibili.com,DIRECT",
            "DOMAIN-SUFFIX,bilivideo.com,DIRECT",
        }
        self.assertTrue(required.issubset(set(self.lines)))

    def test_dns_is_explicit_and_has_no_system_fallback(self) -> None:
        for key, value in build.DNS_SETTINGS:
            line = f"{key} = {value}"
            self.assertEqual(self.lines.count(line), 1, line)
        self.assertNotIn("dns-server = system", self.lines)
        self.assertNotIn("fallback-dns-server = system", self.lines)

    def test_proxy_dns_uses_proxy_tag(self) -> None:
        dns_line = next(line for line in self.lines if line.startswith("dns-server ="))
        fallback_line = next(
            line for line in self.lines if line.startswith("fallback-dns-server =")
        )
        self.assertIn("#proxy", dns_line)
        self.assertIn("#proxy", fallback_line)

    def test_system_traffic_enters_rule_processing(self) -> None:
        self.assertEqual(self.lines.count("bypass-system = false"), 1)
        self.assertNotIn("bypass-system = true", self.lines)

    def test_self_update_url(self) -> None:
        expected = f"update-url = {build.OUTPUT_URL}"
        self.assertEqual(self.lines.count(expected), 1)
        self.assertNotIn(f"update-url = {build.UPSTREAM_URL}", self.lines)


if __name__ == "__main__":
    unittest.main()
