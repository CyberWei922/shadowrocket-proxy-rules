#!/usr/bin/env python3
"""Build the customized Shadowrocket configuration from the upstream file."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys
import urllib.request


REPOSITORY = "CyberWei922/shadowrocket-proxy-rules"
UPSTREAM_URL = (
    "https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/"
    "sr_proxy_banad.conf"
)
OUTPUT_URL = (
    f"https://raw.githubusercontent.com/{REPOSITORY}/main/"
    "dist/sr_proxy_banad_custom.conf"
)

DNS_SETTINGS = (
    ("update-url", OUTPUT_URL),
    ("bypass-system", "false"),
    (
        "skip-proxy",
        "192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, "
        "fe80::/10, fc00::/7, localhost, *.local, *.lan, *.internal, "
        "captive.apple.com",
    ),
    (
        "dns-server",
        "https://1.1.1.1/dns-query#proxy, "
        "https://8.8.8.8/dns-query#proxy",
    ),
    (
        "fallback-dns-server",
        "https://1.0.0.1/dns-query#proxy, "
        "https://8.8.4.4/dns-query#proxy",
    ),
    (
        "direct-dns-server",
        "https://223.5.5.5/dns-query, https://1.12.12.12/dns-query",
    ),
    (
        "proxy-dns-server",
        "https://223.5.5.5/dns-query, https://1.12.12.12/dns-query",
    ),
    ("dns-direct-system", "false"),
    ("dns-fallback-system", "false"),
    ("dns-direct-fallback-proxy", "true"),
    ("hijack-dns", ":53"),
    ("ipv6", "false"),
    ("prefer-ipv6", "false"),
    ("private-ip-answer", "true"),
    ("block-quic", "all-proxy"),
    ("udp-policy-not-supported-behaviour", "REJECT"),
    ("use-local-host-item-for-proxy", "false"),
)

DNS_BEGIN = "# BEGIN MANAGED DNS SETTINGS"
DNS_END = "# END MANAGED DNS SETTINGS"
RULES_BEGIN = "# BEGIN CUSTOM DIRECT RULES"
RULES_END = "# END CUSTOM DIRECT RULES"


class BuildError(RuntimeError):
    pass


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"{REPOSITORY} updater"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    return data.decode("utf-8-sig")


def load_direct_rules(path: pathlib.Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    rules: list[str] = []
    seen: set[str] = set()
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            rules.append(raw.rstrip())
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) < 3 or fields[2] != "DIRECT":
            raise BuildError(f"{path}:{number}: expected a DIRECT rule: {line}")
        normalized = ",".join(fields)
        if normalized in seen:
            raise BuildError(f"{path}:{number}: duplicate rule: {normalized}")
        seen.add(normalized)
        rules.append(normalized)
    return rules


def replace_general_settings(text: str) -> str:
    lines = text.splitlines()
    try:
        general_start = lines.index("[General]")
        rule_start = lines.index("[Rule]")
    except ValueError as exc:
        raise BuildError("upstream must contain [General] and [Rule]") from exc
    if general_start >= rule_start:
        raise BuildError("[General] must appear before [Rule]")

    controlled = {key.lower() for key, _ in DNS_SETTINGS}
    key_pattern = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=")
    kept: list[str] = []
    skipping_old_managed_block = False
    for line in lines[general_start + 1 : rule_start]:
        if line.strip() == DNS_BEGIN:
            skipping_old_managed_block = True
            continue
        if line.strip() == DNS_END:
            skipping_old_managed_block = False
            continue
        if skipping_old_managed_block:
            continue
        match = key_pattern.match(line)
        if match and match.group(1).lower() in controlled:
            continue
        kept.append(line)

    managed = [DNS_BEGIN]
    managed.extend(f"{key} = {value}" for key, value in DNS_SETTINGS)
    managed.append(DNS_END)
    new_general = ["[General]", *managed, "", *kept]

    result = [*lines[:general_start], *new_general, *lines[rule_start:]]
    return "\n".join(result).rstrip() + "\n"


def inject_direct_rules(text: str, direct_rules: list[str]) -> str:
    lines = text.splitlines()
    final_positions = [
        index for index, line in enumerate(lines) if line.strip() == "FINAL,PROXY"
    ]
    if len(final_positions) != 1:
        raise BuildError(
            f"expected exactly one FINAL,PROXY, found {len(final_positions)}"
        )
    if RULES_BEGIN in lines or RULES_END in lines:
        raise BuildError("upstream unexpectedly contains custom rule markers")

    final_index = final_positions[0]
    block = ["", RULES_BEGIN, *direct_rules, RULES_END, ""]
    lines[final_index:final_index] = block
    return "\n".join(lines).rstrip() + "\n"


def build(upstream: str, direct_rules: list[str]) -> str:
    if upstream.count("[Rule]") != 1:
        raise BuildError("upstream must contain exactly one [Rule] section")
    if upstream.count("DOMAIN-SUFFIX,") < 50_000:
        raise BuildError("upstream ad list is unexpectedly small")

    result = replace_general_settings(upstream)
    result = inject_direct_rules(result, direct_rules)
    digest = hashlib.sha256(upstream.encode("utf-8")).hexdigest()
    provenance = (
        f"# Downstream: https://github.com/{REPOSITORY}\n"
        f"# Upstream: {UPSTREAM_URL}\n"
        f"# Upstream-SHA256: {digest}\n"
    )
    if result.startswith("# Shadowrocket:"):
        first_newline = result.index("\n") + 1
        result = result[:first_newline] + provenance + result[first_newline:]
    else:
        result = provenance + result
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-file", type=pathlib.Path)
    parser.add_argument(
        "--rules",
        type=pathlib.Path,
        default=pathlib.Path("rules/direct.list"),
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("dist/sr_proxy_banad_custom.conf"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        upstream = (
            args.upstream_file.read_text(encoding="utf-8-sig")
            if args.upstream_file
            else fetch_text(UPSTREAM_URL)
        )
        direct_rules = load_direct_rules(args.rules)
        output = build(upstream, direct_rules)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8", newline="\n")
    except (BuildError, OSError, UnicodeError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
