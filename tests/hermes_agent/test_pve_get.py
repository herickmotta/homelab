#!/usr/bin/env python3
"""pve-get must work from managed files without TOKEN/SECRET env vars."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "ansible/roles/hermes_agent/files/pve-get"


class PveGetFiles(unittest.TestCase):
    def test_reads_sibling_files_and_calls_curl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            pvedir = root / "pve"
            bindir.mkdir()
            pvedir.mkdir()
            helper = bindir / "pve-get"
            helper.write_text(HELPER.read_text(encoding="utf-8"), encoding="utf-8")
            helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
            (pvedir / "endpoint").write_text("https://192.0.2.10:8006\n", encoding="utf-8")
            (pvedir / "token-id").write_text("hermes@pve!hermes\n", encoding="utf-8")
            (pvedir / "token-secret").write_text("s3cret\n", encoding="utf-8")
            (pvedir / "verify-ssl").write_text("0\n", encoding="utf-8")
            args_file = root / "curl.args"
            curl = bindir / "curl"
            curl.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' \"$@\" > {args_file}\n"
                "printf '%s\\n' '{\"data\":\"ok\"}'\n",
                encoding="utf-8",
            )
            curl.chmod(curl.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{bindir}:{env.get('PATH', '/usr/bin')}"
            for key in list(env):
                if "TOKEN" in key or "SECRET" in key:
                    env.pop(key, None)
            result = subprocess.run(
                [str(helper), "version"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertIn('"data":"ok"', result.stdout)
            args = args_file.read_text(encoding="utf-8")
            self.assertIn("\n-X\nGET\n", f"\n{args}")
            self.assertIn(
                "Authorization: PVEAPIToken=hermes@pve!hermes=s3cret",
                args,
            )
            self.assertIn("https://192.0.2.10:8006/api2/json/version", args)
            self.assertIn("\n-k\n", f"\n{args}")

    def test_refuses_start(self) -> None:
        result = subprocess.run(
            ["sh", str(HELPER), "nodes/pve/qemu/100/status/start"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GET-only", result.stderr)


if __name__ == "__main__":
    unittest.main()
