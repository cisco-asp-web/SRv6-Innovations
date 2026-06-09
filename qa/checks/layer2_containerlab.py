"""
Layer 2 — Containerlab topology & Docker containers.

SSH to topology-host and inspect every expected container.
Uses `docker inspect` (no sudo needed — cisco user is in the docker group).

Checks:
  L2-01 … L2-N   Each expected container is Running with low restart count
  L2-MGT          Management network (mgt-network) exists with correct subnet
"""

import time
from typing import List

from .base import CheckResult, Severity
from .ssh import SSHSession


def _container_check(
    session: SSHSession,
    check_id: str,
    name: str,
    max_restarts: int,
) -> CheckResult:
    fmt = "{{.State.Status}} {{.RestartCount}}"
    out, _, code = session.run(
        f"docker inspect {name} --format='{fmt}' 2>/dev/null", timeout=15
    )

    label = f"container: {name}"

    if code != 0 or not out:
        return CheckResult(id=check_id, name=label, layer=2, severity=Severity.CRITICAL,
                           message="Not found — topology may not be deployed")

    parts = out.split()
    status = parts[0] if parts else "unknown"
    try:
        restarts = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        restarts = 0

    if status != "running":
        sev = Severity.CRITICAL
        msg = f"Status: {status}"
        if status == "exited":
            # get the exit code for a more useful message
            exit_fmt = "{{.State.ExitCode}}"
            ec_out, _, _ = session.run(
                f"docker inspect {name} --format='{exit_fmt}' 2>/dev/null", timeout=10
            )
            exit_code = ec_out.strip()
            msg += f" (exit code {exit_code}"
            if exit_code == "137":
                msg += " — OOM killed, check host RAM"
            msg += ")"
        return CheckResult(id=check_id, name=label, layer=2, severity=sev, message=msg)

    if restarts > max_restarts:
        return CheckResult(id=check_id, name=label, layer=2, severity=Severity.WARNING,
                           message=f"Running but restarted {restarts}x (threshold {max_restarts})")

    return CheckResult(id=check_id, name=label, layer=2, severity=Severity.OK,
                       message=f"Running  (restarts: {restarts})")


def _network_check(session: SSHSession) -> CheckResult:
    out, _, code = session.run(
        "docker network inspect mgt-network --format='{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null",
        timeout=10,
    )
    name = "Docker network: mgt-network"
    if code != 0 or not out:
        return CheckResult(id="L2-MGT", name=name, layer=2, severity=Severity.CRITICAL,
                           message="Network not found — containerlab topology not deployed")
    if "172.20.6.0/24" in out:
        return CheckResult(id="L2-MGT", name=name, layer=2, severity=Severity.OK,
                           message=f"Subnet {out}")
    return CheckResult(id="L2-MGT", name=name, layer=2, severity=Severity.WARNING,
                       message=f"Unexpected subnet: {out}")


def run_container_checks(hosts_config: dict, containers: list, thresholds: dict) -> List[CheckResult]:
    """
    SSH to topology-host and inspect every expected container.
    Returns one CheckResult per container plus one for the management network.
    """
    results: List[CheckResult] = []
    topo = hosts_config["topology_host"]
    max_restarts = thresholds.get("max_container_restarts", 3)

    t0 = time.monotonic()
    session = SSHSession()
    try:
        session.connect(host=topo["ip"], user=topo["user"], password=topo["password"])
    except Exception as exc:
        return [CheckResult(
            id="L2-SSH",
            name=f"SSH → topology-host ({topo['ip']})",
            layer=2,
            severity=Severity.ERROR,
            message=f"Connection failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )]

    with session:
        results.append(_network_check(session))
        for idx, container in enumerate(containers, start=1):
            results.append(_container_check(session, f"L2-{idx:02d}", container, max_restarts))

    return results
