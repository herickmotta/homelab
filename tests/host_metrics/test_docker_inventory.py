#!/usr/bin/env python3
"""Tests for Docker inventory Prometheus textfile metrics."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ansible/roles/host_metrics/files/docker_inventory.py"
PROBES = ROOT / "ansible/roles/host_metrics/templates/host-metrics-probes.j2"


class DockerInventory(unittest.TestCase):
    def test_role_copies_stay_identical(self) -> None:
        host = ROOT / "ansible/roles/host_metrics/files/docker_inventory.py"
        observe = ROOT / "ansible/roles/observability/files/docker_inventory.py"
        self.assertEqual(host.read_text(encoding="utf-8"), observe.read_text(encoding="utf-8"))
    def test_emits_ip_health_restarts_and_gateway(self) -> None:
        containers = [
            {
                "Name": "/mosquitto",
                "State": {"Running": True, "Health": {"Status": "healthy"}},
                "RestartCount": 2,
                "Config": {
                    "Image": "eclipse-mosquitto:2.1.2-alpine",
                    "Labels": {
                        "com.docker.compose.project": "mosquitto",
                        "com.docker.compose.service": "mosquitto",
                        "homelab.role": "mqtt_broker",
                    },
                    "Env": ["MQTT_PASSWORD=super-secret"],
                },
                "HostConfig": {
                    "PortBindings": {
                        "1883/tcp": [{"HostIp": "127.0.0.1", "HostPort": "1883"}]
                    }
                },
                "NetworkSettings": {
                    "Networks": {"mqtt": {"IPAddress": "172.19.0.2"}}
                },
            }
        ]
        networks = [
            {
                "Name": "mqtt",
                "Driver": "bridge",
                "IPAM": {"Config": [{"Gateway": "172.19.0.1", "Subnet": "172.19.0.0/16"}]},
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "containers.json"
            npath = Path(tmp) / "networks.json"
            cpath.write_text(json.dumps(containers), encoding="utf-8")
            npath.write_text(json.dumps(networks), encoding="utf-8")
            env = os.environ.copy()
            env["DOCKER_INVENTORY_CONTAINERS"] = str(cpath)
            env["DOCKER_INVENTORY_NETWORKS"] = str(npath)
            out = subprocess.check_output([sys.executable, str(SCRIPT)], env=env, text=True)
        self.assertIn("homelab_docker_container_running", out)
        self.assertIn('name="mosquitto"', out)
        self.assertIn('ip="172.19.0.2"', out)
        self.assertIn('gateway="172.19.0.1"', out)
        self.assertIn('host_port="1883"', out)
        self.assertIn("homelab_docker_container_restarts", out)
        self.assertNotIn("super-secret", out)
        self.assertNotIn("MQTT_PASSWORD", out)

    def test_probe_template_calls_inventory_when_active(self) -> None:
        text = PROBES.read_text(encoding="utf-8")
        self.assertIn("docker_inventory.py", text)
        self.assertIn("host_metrics_docker_inventory_active", text)


if __name__ == "__main__":
    unittest.main()
