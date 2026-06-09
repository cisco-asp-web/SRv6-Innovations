"""
Layer 8 — End-to-end data-plane tests.

Validates that traffic actually flows through the intended paths.

WAN tests (run via docker exec on topology-host):
  L8-WAN-{n}   IPv4/IPv6 ping from app-container-01 to app-container-07

VM frontend/backend reachability (SSH to VM-00 via jump host):
  L8-VM-{n}    Ping from dc01-vm-00 to XRd frontend / SONiC leaf loopback
"""

import re
import time
from typing import List

from .base import CheckResult, Severity
from .ssh import SSHSession


def _parse_ping(output: str) -> tuple[int, int]:
    """Return (packets_tx, packets_rx) from ping output."""
    m = re.search(r"(\d+) packets transmitted,\s*(\d+)\s*(packets\s+)?received", output)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def _wan_ping(session: SSHSession, check_id: str, desc: str,
              container: str, target: str, ipv6: bool = False) -> CheckResult:
    name = f"E2E ping: {desc}"
    cmd_name = "ping6" if ipv6 else "ping"
    cmd = f"docker exec {container} {cmd_name} -c 5 -W 2 {target} 2>/dev/null"
    out, _, code = session.run(cmd, timeout=30)
    if not out:
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.ERROR,
                           message=f"No output — container may be down")
    tx, rx = _parse_ping(out)
    if tx == 0:
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.ERROR,
                           message="Could not parse ping output", detail=out[:300])
    loss = tx - rx
    if loss == tx:
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.CRITICAL,
                           message=f"100% loss — {target} unreachable")
    if loss > 0:
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.WARNING,
                           message=f"{rx}/{tx} packets received ({loss} lost)")
    return CheckResult(id=check_id, name=name, layer=8, severity=Severity.OK,
                       message=f"{rx}/{tx} packets received")


def _vm_ping(check_id: str, desc: str, vm_ip: str, target: str,
             jump_ip: str, jump_user: str, jump_pass: str,
             ipv6: bool = False, interface: str = "") -> CheckResult:
    name = f"E2E ping: {desc}"
    t0 = time.monotonic()
    session = SSHSession()
    try:
        session.connect(
            host=vm_ip,
            user="cisco",
            password="cisco123",
            jump_host=jump_ip,
            jump_user=jump_user,
            jump_password=jump_pass,
        )
    except Exception as exc:
        return CheckResult(
            id=check_id, name=name, layer=8, severity=Severity.ERROR,
            message=f"SSH to VM failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

    iface_flag = f" -I {interface}" if interface else ""
    cmd_name = "ping6" if ipv6 else "ping"
    cmd = f"{cmd_name} -c 5 -W 2{iface_flag} {target} 2>/dev/null"

    try:
        out, _, _ = session.run(cmd, timeout=30)
    except Exception as exc:
        session.close()
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.ERROR,
                           message=f"ping failed: {exc}")
    finally:
        session.close()

    if not out:
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.ERROR,
                           message="No output")
    tx, rx = _parse_ping(out)
    if tx == 0:
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.ERROR,
                           message="Could not parse ping output", detail=out[:300])
    loss = tx - rx
    if loss == tx:
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.CRITICAL,
                           message=f"100% loss — {target} unreachable")
    if loss > 0:
        return CheckResult(id=check_id, name=name, layer=8, severity=Severity.WARNING,
                           message=f"{rx}/{tx} packets received ({loss} lost)")
    return CheckResult(id=check_id, name=name, layer=8, severity=Severity.OK,
                       message=f"{rx}/{tx} packets received")


def run_e2e_checks(hosts_config: dict, e2e_config: dict) -> List[CheckResult]:
    """
    Run WAN pings (docker exec on topology-host) and VM pings (SSH via jump host).
    """
    if not e2e_config:
        return []

    topo = hosts_config["topology_host"]
    results: List[CheckResult] = []

    # ── WAN pings (docker exec on topology-host) ───────────────────────────────
    wan_tests = e2e_config.get("wan_tests", [])
    if wan_tests:
        t0 = time.monotonic()
        session = SSHSession()
        try:
            session.connect(host=topo["ip"], user=topo["user"], password=topo["password"])
        except Exception as exc:
            results.append(CheckResult(
                id="L8-SSH", name=f"SSH → topology-host ({topo['ip']})",
                layer=8, severity=Severity.ERROR,
                message=f"Connection failed: {exc}",
                duration_ms=int((time.monotonic() - t0) * 1000),
            ))
            wan_tests = []

        if session._main:
            with session:
                for idx, test in enumerate(wan_tests, start=1):
                    check_id = f"L8-WAN-{idx:02d}"
                    desc = test.get("description", f"wan-test-{idx}")
                    container = test.get("from_container", "app-container-01")
                    if "to_ip6" in test:
                        results.append(_wan_ping(session, check_id, desc, container,
                                                 test["to_ip6"], ipv6=True))
                    else:
                        results.append(_wan_ping(session, check_id, desc, container,
                                                 test.get("to_ip", "")))

    # ── VM pings (SSH topology-host → VM-00 → ping) ────────────────────────────
    for idx, test in enumerate(e2e_config.get("vm_pings", []), start=1):
        check_id = f"L8-VM-{idx:02d}"
        results.append(_vm_ping(
            check_id=check_id,
            desc=test.get("description", f"vm-ping-{idx}"),
            vm_ip=test["from_vm_ip"],
            target=test.get("to_ip6") or test.get("to_ip", ""),
            jump_ip=topo["ip"],
            jump_user=topo["user"],
            jump_pass=topo["password"],
            ipv6="to_ip6" in test,
            interface=test.get("interface", ""),
        ))

    return results
