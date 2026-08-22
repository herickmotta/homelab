#!/usr/bin/env python3
"""Unit tests for NAS health evaluation."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "roles" / "nas_server" / "files" / "homelab-nas-health"


def load_module():
    loader = importlib.machinery.SourceFileLoader("homelab_nas_health", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


health = load_module()

EXPECTED = {
    "mounts": [
        {"mapping": "example-personal", "path": "/srv/personal", "share": "personal", "read_only": False},
        {"mapping": "example-media", "path": "/srv/media", "share": "media", "read_only": False},
    ]
}

SMB_CONF = """
[global]
   map to guest = Never
   server min protocol = SMB3
"""


def observed_ok():
    return {
        "mounts": [
            {
                "mapping": "example-personal",
                "share": "personal",
                "path": "/srv/personal",
                "read_only": False,
                "exists": True,
                "mount": {"fstype": "virtiofs", "source": "example-personal", "options": "rw"},
                "usage": {"size_bytes": 100, "avail_bytes": 80, "used_bytes": 20},
            },
            {
                "mapping": "example-media",
                "share": "media",
                "path": "/srv/media",
                "read_only": False,
                "exists": True,
                "mount": {"fstype": "virtiofs", "source": "example-media", "options": "rw"},
                "usage": {"size_bytes": 200, "avail_bytes": 150, "used_bytes": 50},
            },
        ],
        "smbd_active": True,
        "nmbd_active": False,
        "smb_port_open": True,
        "smb_conf": SMB_CONF,
    }


class NasHealthTests(unittest.TestCase):
    def test_healthy_nas(self):
        report = health.evaluate(EXPECTED, observed_ok())
        self.assertEqual(report["status"], health.STATUS_OK)
        self.assertEqual(health.EXIT_BY_STATUS[report["status"]], 0)

    def test_missing_virtiofs_is_critical(self):
        observed = observed_ok()
        observed["mounts"][0]["mount"] = {}
        report = health.evaluate(EXPECTED, observed)
        self.assertEqual(report["status"], health.STATUS_CRITICAL)
        self.assertTrue(any(alert["code"] == "virtiofs_unmounted" for alert in report["alerts"]))

    def test_duplicate_share_paths_are_critical(self):
        expected = {
            "mounts": [
                {"mapping": "example-personal", "path": "/srv/data", "share": "personal"},
                {"mapping": "example-media", "path": "/srv/data", "share": "media"},
            ]
        }
        report = health.evaluate(expected, observed_ok())
        self.assertEqual(report["status"], health.STATUS_CRITICAL)
        self.assertTrue(any(alert["code"] == "share_path_collision" for alert in report["alerts"]))

    def test_guest_access_without_smb3_is_critical(self):
        observed = observed_ok()
        observed["smb_conf"] = "[global]\nmap to guest = Bad User\n"
        report = health.evaluate(EXPECTED, observed)
        self.assertEqual(report["status"], health.STATUS_CRITICAL)
        codes = {alert["code"] for alert in report["alerts"]}
        self.assertIn("smb3_required", codes)
        self.assertIn("smb_guest_enabled", codes)

    def test_zero_virtiofs_is_not_a_nas_configuration(self):
        report = health.evaluate({"mounts": []}, {"mounts": [], "smbd_active": True, "nmbd_active": False, "smb_port_open": True, "smb_conf": SMB_CONF})
        self.assertEqual(report["status"], health.STATUS_OK)


if __name__ == "__main__":
    unittest.main()
