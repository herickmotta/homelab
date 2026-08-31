#!/usr/bin/env python3
"""Host TCP probes must connect without writing an application payload."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBES = ROOT / "ansible/roles/host_metrics/templates/host-metrics-probes.j2"


def test_local_tcp_probe_is_connect_only() -> None:
    text = PROBES.read_text(encoding="utf-8")
    assert "echo >/dev/tcp/" not in text
    assert "exec 3<>/dev/tcp/" in text
    assert 'address="{{ probe.address }}"' in text


if __name__ == "__main__":
    test_local_tcp_probe_is_connect_only()
    print("local tcp probe is connect-only")
