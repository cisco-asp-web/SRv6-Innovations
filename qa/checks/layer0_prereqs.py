"""
Layer 0 — Prerequisites & host reachability.

Checks run directly from the operator's Mac (or any host with network access
to dCloud). No jump host is needed for topology-host and jalapeno-host —
they are the outermost reachable nodes.

Checks:
  L0-01  SSH → topology-host
  L0-02  SSH → jalapeno-host
  L0-03  Docker running on topology-host
  L0-04  libvirtd running on topology-host
  L0-05  Docker running on jalapeno-host
  L0-06  Free disk space on topology-host (> threshold GB)
  L0-07  XRd Docker image present on topology-host
  L0-08  SONiC Docker image present on topology-host
"""

import time
from typing import List, Optional, Tuple

from .base import CheckResult, Severity
from .ssh import SSHSession


# ── Helpers ───────────────────────────────────────────────────────────────────

def _connect(host: str, user: str, password: str) -> Tuple[Optional[SSHSession], CheckResult, str]:
    """Try to open an SSH connection. Returns (session_or_None, result, check_id_prefix)."""
    label = f"SSH → {host}"
    t0 = time.monotonic()
    session = SSHSession()
    try:
        session.connect(host=host, user=user, password=password)
        elapsed = int((time.monotonic() - t0) * 1000)
        return session, CheckResult(
            id="",  # caller sets id
            name=label,
            layer=0,
            severity=Severity.OK,
            message=f"Connected ({elapsed}ms)",
            duration_ms=elapsed,
        ), label
    except Exception as exc:
        session.close()
        elapsed = int((time.monotonic() - t0) * 1000)
        return None, CheckResult(
            id="",
            name=label,
            layer=0,
            severity=Severity.ERROR,
            message=f"Connection failed: {exc}",
            duration_ms=elapsed,
        ), label


def _service(session: SSHSession, check_id: str, name: str, service: str) -> CheckResult:
    out, _, _ = session.run(f"systemctl is-active {service}", timeout=10)
    if out == "active":
        return CheckResult(id=check_id, name=name, layer=0, severity=Severity.OK, message="active")
    return CheckResult(
        id=check_id, name=name, layer=0, severity=Severity.CRITICAL,
        message=f"Not active — got: '{out}'"
    )


def _disk(session: SSHSession, check_id: str, path: str, min_gb: int) -> CheckResult:
    # df with -BG reports sizes in whole gigabytes; field 4 is "Avail"
    out, _, code = session.run(
        f"df -BG {path} | awk 'NR==2{{gsub(/G/,\"\"); print $4+0}}'", timeout=10
    )
    name = f"Disk space {path}"
    if code != 0 or not out.isdigit():
        return CheckResult(id=check_id, name=name, layer=0, severity=Severity.ERROR,
                           message=f"Could not read disk usage: {out}")
    avail = int(out)
    if avail >= min_gb:
        return CheckResult(id=check_id, name=name, layer=0, severity=Severity.OK,
                           message=f"{avail}GB available")
    return CheckResult(id=check_id, name=name, layer=0, severity=Severity.WARNING,
                       message=f"Only {avail}GB free (minimum {min_gb}GB)")


def _image(session: SSHSession, check_id: str, image: str) -> CheckResult:
    name = f"Docker image: {image}"
    _, _, code = session.run(f"docker image inspect {image} >/dev/null 2>&1", timeout=15)
    if code == 0:
        return CheckResult(id=check_id, name=name, layer=0, severity=Severity.OK, message="Present")
    return CheckResult(
        id=check_id, name=name, layer=0, severity=Severity.CRITICAL,
        message="Not found — containerlab topology will fail to start"
    )


# ── Public entry point ────────────────────────────────────────────────────────

def run_prereq_checks(hosts_config: dict, thresholds: dict, docker_images: list) -> List[CheckResult]:
    """
    Connect to topology-host and jalapeno-host and run prerequisite checks.
    Returns one CheckResult per check.
    """
    results: List[CheckResult] = []
    min_disk = thresholds.get("min_disk_gb", 20)

    topo = hosts_config["topology_host"]
    jal = hosts_config.get("jalapeno_host")

    # ── topology-host ─────────────────────────────────────────────────────────
    session, r = _connect(topo["ip"], topo["user"], topo["password"])[:2]
    r.id = "L0-01"
    results.append(r)

    if session:
        with session:
            results.append(_service(session, "L0-03", "Docker running (topology-host)", "docker"))
            results.append(_service(session, "L0-04", "libvirtd running (topology-host)", "libvirtd"))
            results.append(_disk(session, "L0-06", "/home/cisco", min_disk))
            for idx, image in enumerate(docker_images, start=7):
                results.append(_image(session, f"L0-{idx:02d}", image))

    # ── jalapeno-host ─────────────────────────────────────────────────────────
    if jal:
        session, r = _connect(jal["ip"], jal["user"], jal["password"])[:2]
        r.id = "L0-02"
        results.append(r)
        if session:
            with session:
                results.append(_service(session, "L0-05", "Docker running (jalapeno-host)", "docker"))

    return results
