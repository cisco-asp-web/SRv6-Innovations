"""
Layer 3 — XRd routing protocols (ISIS / BGP / SRv6).

SSH to topology-host and runs IOS-XR CLI commands via docker exec.
Each command is piped into /pkg/bin/xr_cli.sh running inside the container.

Checks per router:
  L3-ISIS-{n}   ISIS neighbor count ≥ min_isis_neighbors (default 1)
  L3-SRV6-{n}   SRv6 locator present and Active with expected prefix

Checks on route reflectors (role: rr):
  L3-BGP-{n}    BGP established session count ≥ min_bgp_sessions
"""

import re
import time
from typing import List

from .base import CheckResult, Severity
from .ssh import SSHSession

_XR_PROMPT_RE = re.compile(r"^RP/\d+/\w+/\w+:\S+#", re.MULTILINE)


def _xr_exec(session: SSHSession, container: str, command: str, timeout: int = 20) -> str:
    """Run one IOS-XR CLI command inside a container; return stripped output."""
    raw, _, _ = session.run(
        f"echo '{command}' | docker exec -i {container} /pkg/bin/xr_cli.sh 2>/dev/null",
        timeout=timeout,
    )
    filtered = "\n".join(
        line for line in raw.splitlines()
        if not _XR_PROMPT_RE.match(line)
    )
    return filtered.strip()


def _isis_check(session: SSHSession, node: dict, idx: int) -> CheckResult:
    container = node["container"]
    check_id = f"L3-ISIS-{idx:02d}"
    name = f"ISIS neighbors: {container}"
    out = _xr_exec(session, container, "show isis neighbors")
    if not out:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.ERROR,
                           message="No output — container CLI unavailable or not yet ready")
    up = len(re.findall(r"\bUp\b", out))
    threshold = node.get("min_isis_neighbors", 1)
    if up == 0:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.CRITICAL,
                           message="0 ISIS neighbors Up", detail=out[:400])
    if up < threshold:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.WARNING,
                           message=f"{up} neighbor(s) Up (expected ≥ {threshold})")
    return CheckResult(id=check_id, name=name, layer=3, severity=Severity.OK,
                       message=f"{up} neighbor(s) Up")


def _bgp_check(session: SSHSession, node: dict, idx: int) -> CheckResult:
    container = node["container"]
    check_id = f"L3-BGP-{idx:02d}"
    name = f"BGP sessions: {container}"
    out = _xr_exec(session, container, "show bgp summary")
    if not out:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.ERROR,
                           message="No output")
    estab = sum(1 for line in out.splitlines() if re.search(r"\bEstab\b", line))
    threshold = node.get("min_bgp_sessions", 1)
    if estab == 0:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.CRITICAL,
                           message="0 BGP sessions Established", detail=out[:400])
    if estab < threshold:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.WARNING,
                           message=f"{estab} session(s) Established (expected ≥ {threshold})")
    return CheckResult(id=check_id, name=name, layer=3, severity=Severity.OK,
                       message=f"{estab} session(s) Established")


def _srv6_check(session: SSHSession, node: dict, idx: int) -> CheckResult:
    container = node["container"]
    expected = node.get("locator", "")
    check_id = f"L3-SRV6-{idx:02d}"
    name = f"SRv6 locator: {container}"
    out = _xr_exec(session, container, "show segment-routing srv6 locators")
    if not out:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.ERROR,
                           message="No output")
    if "Active" not in out:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.CRITICAL,
                           message="No active SRv6 locator found", detail=out[:400])
    if expected and expected not in out:
        return CheckResult(id=check_id, name=name, layer=3, severity=Severity.WARNING,
                           message=f"Locator active but expected prefix {expected} missing")
    return CheckResult(id=check_id, name=name, layer=3, severity=Severity.OK,
                       message=f"Active ({expected})" if expected else "Active")


def run_xrd_checks(hosts_config: dict, xrd_nodes: list) -> List[CheckResult]:
    """SSH to topology-host and validate XRd routing protocols via docker exec."""
    if not xrd_nodes:
        return []

    topo = hosts_config["topology_host"]
    t0 = time.monotonic()
    session = SSHSession()
    try:
        session.connect(host=topo["ip"], user=topo["user"], password=topo["password"])
    except Exception as exc:
        return [CheckResult(
            id="L3-SSH", name=f"SSH → topology-host ({topo['ip']})",
            layer=3, severity=Severity.ERROR,
            message=f"Connection failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )]

    results: List[CheckResult] = []
    with session:
        for idx, node in enumerate(xrd_nodes, start=1):
            results.append(_isis_check(session, node, idx))
            if node.get("role") == "rr":
                results.append(_bgp_check(session, node, idx))
            results.append(_srv6_check(session, node, idx))

    return results
