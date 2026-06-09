"""
Layer 6 — Observability stack (TIG: Telegraf / InfluxDB / Grafana).

SSH to topology-host and:
  - Inspect each TIG container with 'docker inspect'
  - HTTP health-check InfluxDB and Grafana from inside topology-host
    (TIG containers are on mgt-network 172.20.6.0/24, not reachable directly from Mac)

Checks:
  L6-{n}       Each TIG container Running
  L6-INFLUX    InfluxDB /health returns {"status":"pass"}
  L6-GRAFANA   Grafana HTTP returns 200
"""

import time
from typing import List

from .base import CheckResult, Severity
from .ssh import SSHSession


def _container_check(session: SSHSession, check_id: str, name: str) -> CheckResult:
    fmt = "{{.State.Status}}"
    out, _, code = session.run(
        f"docker inspect {name} --format='{fmt}' 2>/dev/null", timeout=15
    )
    label = f"container: {name}"
    if code != 0 or not out:
        return CheckResult(id=check_id, name=label, layer=6, severity=Severity.CRITICAL,
                           message="Not found — TIG stack may not be deployed")
    if out.strip() == "running":
        return CheckResult(id=check_id, name=label, layer=6, severity=Severity.OK,
                           message="Running")
    return CheckResult(id=check_id, name=label, layer=6, severity=Severity.CRITICAL,
                       message=f"Status: {out.strip()}")


def _http_check(session: SSHSession, check_id: str, label: str, url: str,
                expect_substr: str = "", expect_code: str = "200") -> CheckResult:
    if expect_substr:
        cmd = f"curl -s --connect-timeout 5 {url}"
    else:
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' --connect-timeout 5 {url}"

    out, _, code = session.run(cmd, timeout=15)
    if code != 0 or not out:
        return CheckResult(id=check_id, name=label, layer=6, severity=Severity.CRITICAL,
                           message=f"curl failed (exit {code}) — service may be down")

    if expect_substr and expect_substr not in out:
        return CheckResult(id=check_id, name=label, layer=6, severity=Severity.CRITICAL,
                           message=f"Unexpected response — missing '{expect_substr}'",
                           detail=out[:300])

    if not expect_substr and out.strip() != expect_code:
        return CheckResult(id=check_id, name=label, layer=6, severity=Severity.CRITICAL,
                           message=f"HTTP {out.strip()} (expected {expect_code})")

    return CheckResult(id=check_id, name=label, layer=6, severity=Severity.OK,
                       message="OK")


def run_tig_checks(hosts_config: dict, tig_config: dict) -> List[CheckResult]:
    """
    SSH to topology-host and validate TIG stack containers and HTTP endpoints.
    """
    if not tig_config:
        return []

    topo = hosts_config["topology_host"]
    t0 = time.monotonic()
    session = SSHSession()
    try:
        session.connect(host=topo["ip"], user=topo["user"], password=topo["password"])
    except Exception as exc:
        return [CheckResult(
            id="L6-SSH", name=f"SSH → topology-host ({topo['ip']})",
            layer=6, severity=Severity.ERROR,
            message=f"Connection failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )]

    results: List[CheckResult] = []
    with session:
        containers = tig_config.get("containers", [])
        for idx, name in enumerate(containers, start=1):
            results.append(_container_check(session, f"L6-{idx:02d}", name))

        influx_url = tig_config.get("influxdb_url", "")
        if influx_url:
            results.append(_http_check(
                session, "L6-INFLUX", f"InfluxDB health ({influx_url})",
                f"{influx_url}/health", expect_substr='"pass"',
            ))

        grafana_url = tig_config.get("grafana_url", "")
        if grafana_url:
            results.append(_http_check(
                session, "L6-GRAFANA", f"Grafana HTTP ({grafana_url})",
                grafana_url, expect_code="200",
            ))

    return results
