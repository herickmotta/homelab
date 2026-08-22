#!/usr/bin/env python3
"""Unit tests for host storage health evaluation."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "roles" / "proxmox_host_storage" / "files" / "homelab-storage-health"


def load_module():
    loader = importlib.machinery.SourceFileLoader("homelab_storage_health", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


health = load_module()

ZPOOL_STATUS = """\
  pool: iron
 state: ONLINE
  scan: scrub repaired 0B in 00:10:00 with 0 errors on Sun Aug  1 04:10:00 2026
config:

	NAME                                          STATE     READ WRITE CKSUM
	iron                                          ONLINE       0     0     0
	  raidz1-0                                    ONLINE       0     0     0
	    /dev/disk/by-id/ata-EXAMPLE-FAKEIRON01    ONLINE       0     0     0
	    /dev/disk/by-id/ata-EXAMPLE-FAKEIRON02    ONLINE       0     0     0
	    /dev/disk/by-id/ata-EXAMPLE-FAKEIRON03    ONLINE       0     0     0

errors: No known data errors

  pool: volatile
 state: ONLINE
  scan: none requested
config:

	NAME                                          STATE     READ WRITE CKSUM
	volatile                                      ONLINE       0     0     0
	  /dev/disk/by-id/ata-EXAMPLE-FAKEVOL01       ONLINE       0     0     0
"""

EXPECTED = {
    "pools": {
        "iron": {
            "name": "iron",
            "topology": "raidz1",
            "data_class": "durable",
            "disks": [
                {"serial": "FAKEIRON01", "by_id": "/dev/disk/by-id/ata-EXAMPLE-FAKEIRON01"},
                {"serial": "FAKEIRON02", "by_id": "/dev/disk/by-id/ata-EXAMPLE-FAKEIRON02"},
                {"serial": "FAKEIRON03", "by_id": "/dev/disk/by-id/ata-EXAMPLE-FAKEIRON03"},
            ],
        },
        "volatile": {
            "name": "volatile",
            "topology": "stripe",
            "data_class": "disposable",
            "disks": [
                {
                    "serial": "FAKEVOL01",
                    "by_id": "/dev/disk/by-id/ata-EXAMPLE-FAKEVOL01",
                    "accepted_degraded": True,
                }
            ],
        },
    },
    "datasets": {
        "personal": {
            "dataset": "iron/personal",
            "pool": "iron",
            "mountpoint": "/srv/example/iron/personal",
            "class": "important_unbacked",
        },
        "frigate": {
            "dataset": "volatile/frigate",
            "pool": "volatile",
            "mountpoint": "/srv/example/volatile/frigate",
            "class": "disposable",
        },
    },
}


def observed_ok():
    return {
        "disks": [
            {
                "serial": "FAKEIRON01",
                "pool": "iron",
                "declared_by_id": "/dev/disk/by-id/ata-EXAMPLE-FAKEIRON01",
                "observed_by_id": ["/dev/disk/by-id/ata-EXAMPLE-FAKEIRON01"],
                "accepted_degraded": False,
                "data_class": "durable",
                "smart": {"serial": "FAKEIRON01", "passed": True, "reallocated": 0, "pending": 0, "uncorrectable": 0},
            },
            {
                "serial": "FAKEIRON02",
                "pool": "iron",
                "declared_by_id": "/dev/disk/by-id/ata-EXAMPLE-FAKEIRON02",
                "observed_by_id": ["/dev/disk/by-id/ata-EXAMPLE-FAKEIRON02"],
                "accepted_degraded": False,
                "data_class": "durable",
                "smart": {"serial": "FAKEIRON02", "passed": True, "reallocated": 0, "pending": 0, "uncorrectable": 0},
            },
            {
                "serial": "FAKEIRON03",
                "pool": "iron",
                "declared_by_id": "/dev/disk/by-id/ata-EXAMPLE-FAKEIRON03",
                "observed_by_id": ["/dev/disk/by-id/ata-EXAMPLE-FAKEIRON03"],
                "accepted_degraded": False,
                "data_class": "durable",
                "smart": {"serial": "FAKEIRON03", "passed": True, "reallocated": 0, "pending": 0, "uncorrectable": 0},
            },
            {
                "serial": "FAKEVOL01",
                "pool": "volatile",
                "declared_by_id": "/dev/disk/by-id/ata-EXAMPLE-FAKEVOL01",
                "observed_by_id": ["/dev/disk/by-id/ata-EXAMPLE-FAKEVOL01"],
                "accepted_degraded": True,
                "data_class": "disposable",
                "smart": {"serial": "FAKEVOL01", "passed": True, "reallocated": 12, "pending": 0, "uncorrectable": 1},
            },
        ],
        "pools_status": health.parse_zpool_status(ZPOOL_STATUS),
        "pools_list": {
            "iron": {"health": "ONLINE", "size_bytes": 12, "alloc_bytes": 1, "free_bytes": 11},
            "volatile": {"health": "ONLINE", "size_bytes": 4, "alloc_bytes": 1, "free_bytes": 3},
        },
        "datasets": {
            "iron/personal": {
                "mounted": True,
                "mountpoint": "/srv/example/iron/personal",
                "used_bytes": 1,
                "avail_bytes": 10,
            },
            "volatile/frigate": {
                "mounted": True,
                "mountpoint": "/srv/example/volatile/frigate",
                "used_bytes": 1,
                "avail_bytes": 3,
            },
        },
    }


class StorageHealthTests(unittest.TestCase):
    def test_parses_raidz1_and_stripe(self):
        parsed = health.parse_zpool_status(ZPOOL_STATUS)
        self.assertEqual(parsed["iron"]["topology"], "raidz1")
        self.assertEqual(len(parsed["iron"]["devices"]), 3)
        self.assertEqual(parsed["volatile"]["topology"], "stripe")
        self.assertEqual(parsed["volatile"]["devices"][0]["path"].endswith("FAKEVOL01"), True)

    def test_healthy_report_includes_known_degraded_volatile_disk(self):
        report = health.evaluate(EXPECTED, observed_ok())
        self.assertIn(report["status"], {health.STATUS_OK, health.STATUS_WARNING})
        codes = {alert["code"] for alert in report["alerts"]}
        self.assertNotIn("pool_missing", codes)
        self.assertNotIn("serial_missing", codes)
        self.assertIn("smart_reallocated", codes)

    def test_missing_iron_pool_is_critical(self):
        observed = observed_ok()
        observed["pools_list"].pop("iron")
        observed["pools_status"].pop("iron")
        report = health.evaluate(EXPECTED, observed)
        self.assertEqual(report["status"], health.STATUS_CRITICAL)
        self.assertEqual(health.EXIT_BY_STATUS[report["status"]], 2)

    def test_foreign_disk_in_iron_is_critical(self):
        observed = observed_ok()
        observed["pools_status"]["iron"]["devices"].append(
            {"path": "/dev/disk/by-id/ata-EXAMPLE-FAKEVOL01", "state": "ONLINE"}
        )
        report = health.evaluate(EXPECTED, observed)
        self.assertEqual(report["status"], health.STATUS_CRITICAL)
        self.assertTrue(any(alert["code"] == "pool_membership_mismatch" for alert in report["alerts"]))

    def test_prometheus_omits_secrets(self):
        report = health.evaluate(EXPECTED, observed_ok())
        text = health.prometheus_text(report)
        self.assertIn("homelab_storage_healthy", text)
        self.assertNotIn("password", text)
        self.assertNotIn("smtp", text)


if __name__ == "__main__":
    unittest.main()
