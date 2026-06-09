"""
Layer 1 — KVM virtual machines.

SSH to topology-host and run libvirt + bridge checks from there.
The three dc01-vm-XX instances are KVM guests that form the Kubernetes cluster.

Checks:
  L1-01  dc01-vm-00 defined and running (virsh)
  L1-02  dc01-vm-01 defined and running
  L1-03  dc01-vm-02 defined and running
  L1-04  Frontend network bridges UP (dc01-vm-XX-fe)
  L1-05  Backend  network bridges UP (dc01-vm-XX-be)
"""

import time
from typing import List

from .base import CheckResult, Severity
from .ssh import SSHSession


_VMS = ["dc01-vm-00", "dc01-vm-01", "dc01-vm-02"]
_FE_BRIDGES = ["dc01-vm-00-fe", "dc01-vm-01-fe", "dc01-vm-02-fe"]
_BE_BRIDGES = ["dc01-vm-00-be", "dc01-vm-01-be", "dc01-vm-02-be"]


def _vm_check(session: SSHSession, check_id: str, vm: str, password: str) -> CheckResult:
    name = f"KVM: {vm}"
    # virsh is typically restricted to the libvirt group; use sudo to be safe
    out, _, code = session.sudo_run(f"virsh domstate {vm}", password=password)
    if code != 0:
        return CheckResult(id=check_id, name=name, layer=1, severity=Severity.CRITICAL,
                           message=f"Domain not found or virsh error (exit {code})")
    state = out.strip().lower()
    if state == "running":
        return CheckResult(id=check_id, name=name, layer=1, severity=Severity.OK,
                           message="running")
    return CheckResult(id=check_id, name=name, layer=1, severity=Severity.CRITICAL,
                       message=f"State: {state} (expected: running)")


def _bridges_check(session: SSHSession, check_id: str, bridges: List[str], label: str) -> CheckResult:
    name = f"Network bridges UP ({label})"
    # ip link show returns state UP/DOWN/UNKNOWN; count how many are UP
    bridge_list = " ".join(bridges)
    out, _, _ = session.run(f"ip link show {bridge_list} 2>/dev/null | grep -c 'state UP'", timeout=10)
    try:
        up_count = int(out.strip())
    except ValueError:
        up_count = 0

    if up_count == len(bridges):
        return CheckResult(id=check_id, name=name, layer=1, severity=Severity.OK,
                           message=f"All {len(bridges)} UP")
    return CheckResult(id=check_id, name=name, layer=1, severity=Severity.CRITICAL,
                       message=f"Only {up_count}/{len(bridges)} UP — run infrastructure/vms/bridges.sh")


def run_kvm_checks(hosts_config: dict) -> List[CheckResult]:
    """
    SSH to topology-host and validate KVM VM state and network bridges.
    Returns a list of CheckResults; a single ERROR result is returned if SSH fails.
    """
    results: List[CheckResult] = []
    topo = hosts_config["topology_host"]

    t0 = time.monotonic()
    session = SSHSession()
    try:
        session.connect(host=topo["ip"], user=topo["user"], password=topo["password"])
    except Exception as exc:
        return [CheckResult(
            id="L1-SSH",
            name=f"SSH → topology-host ({topo['ip']})",
            layer=1,
            severity=Severity.ERROR,
            message=f"Connection failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )]

    with session:
        for idx, vm in enumerate(_VMS, start=1):
            results.append(_vm_check(session, f"L1-0{idx}", vm, topo["password"]))

        results.append(_bridges_check(session, "L1-04", _FE_BRIDGES, "frontend fe"))
        results.append(_bridges_check(session, "L1-05", _BE_BRIDGES, "backend be"))

    return results
