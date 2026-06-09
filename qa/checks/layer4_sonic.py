"""
Layer 4 — SONiC DC fabric (FRR / BGP).

For each SONiC node, creates an SSH session through topology-host as a jump
host, then runs 'sudo vtysh -c "show bgp summary"' inside the SONiC VM.

A single check per node covers both FRR health (if vtysh fails, FRR is down)
and BGP session state (counts established sessions against the threshold).

Checks:
  L4-BGP-{n}   BGP established session count ≥ min_bgp_sessions
"""

import re
import time
from typing import List

from .base import CheckResult, Severity
from .ssh import SSHSession


_DOWN_STATES = frozenset({
    "Active", "Idle", "Connect", "OpenSent", "OpenConfirm", "Clearing", "Deleted",
})


def _count_established(output: str) -> int:
    """Count established BGP peers in 'show bgp summary' (vtysh/FRR format)."""
    count = 0
    for line in output.splitlines():
        parts = line.split()
        if not parts:
            continue
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", parts[0]):
            continue
        # Established peers show a numeric prefix count; down peers show state words
        if not any(p in _DOWN_STATES for p in parts):
            count += 1
    return count


def _bgp_check(jump_ip: str, jump_user: str, jump_pass: str, node: dict, idx: int) -> CheckResult:
    check_id = f"L4-BGP-{idx:02d}"
    name = f"BGP sessions: {node['name']}"
    threshold = node.get("min_bgp_sessions", 1)
    t0 = time.monotonic()

    session = SSHSession()
    try:
        session.connect(
            host=node["mgmt_ip"],
            user="cisco",
            password="cisco123",
            jump_host=jump_ip,
            jump_user=jump_user,
            jump_password=jump_pass,
        )
    except Exception as exc:
        return CheckResult(
            id=check_id, name=name, layer=4, severity=Severity.ERROR,
            message=f"SSH failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

    try:
        out, _, code = session.sudo_run(
            'vtysh -c "show bgp summary"', password="cisco123", timeout=20
        )
    except Exception as exc:
        return CheckResult(
            id=check_id, name=name, layer=4, severity=Severity.ERROR,
            message=f"vtysh failed: {exc}",
        )
    finally:
        session.close()

    if code != 0 or not out or "bgp" not in out.lower():
        return CheckResult(
            id=check_id, name=name, layer=4, severity=Severity.CRITICAL,
            message="FRR not running or vtysh unavailable", detail=out[:400],
        )

    estab = _count_established(out)
    if estab == 0:
        return CheckResult(id=check_id, name=name, layer=4, severity=Severity.CRITICAL,
                           message="0 BGP sessions Established", detail=out[:400])
    if estab < threshold:
        return CheckResult(id=check_id, name=name, layer=4, severity=Severity.WARNING,
                           message=f"{estab} session(s) Established (expected ≥ {threshold})")
    return CheckResult(id=check_id, name=name, layer=4, severity=Severity.OK,
                       message=f"{estab} session(s) Established")


def run_sonic_checks(hosts_config: dict, sonic_nodes: list) -> List[CheckResult]:
    """
    SSH through topology-host to each SONiC node and validate FRR BGP state.
    One result per node.
    """
    if not sonic_nodes:
        return []

    topo = hosts_config["topology_host"]
    results: List[CheckResult] = []
    for idx, node in enumerate(sonic_nodes, start=1):
        results.append(_bgp_check(
            jump_ip=topo["ip"],
            jump_user=topo["user"],
            jump_pass=topo["password"],
            node=node,
            idx=idx,
        ))
    return results
