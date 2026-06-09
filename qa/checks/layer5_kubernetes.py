"""
Layer 5 — Kubernetes certificate expiry checks.

Connects to the K8s control-plane via SSH (with optional jump host) and runs
`kubeadm certs check-expiration`, then parses each certificate's expiry date
against the configured warning/critical thresholds.

Sample kubeadm output:
    CERTIFICATE                EXPIRES                  RESIDUAL TIME   ...
    admin.conf                 Jun 08, 2027 12:00 UTC   364d            ...
    apiserver                  Jun 06, 2026 12:00 UTC   <invalid>       ...  ← expired

    CERTIFICATE AUTHORITY   EXPIRES                  RESIDUAL TIME   ...
    ca                      Jun 06, 2036 12:00 UTC   9y              ...
"""

import re
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from .base import CheckResult, Severity
from .ssh import SSHSession


_EXPIRY_FMT = "%b %d, %Y %H:%M UTC"
_DATE_RE = re.compile(r"(\w{3}\s+\d{2},\s+\d{4}\s+\d{2}:\d{2}\s+UTC)")


def _parse_output(raw: str) -> List[Tuple[str, Optional[datetime]]]:
    """Return (cert_name, expiry_or_None) for every certificate row found."""
    results = []
    in_table = False

    for line in raw.splitlines():
        stripped = line.strip()
        if "EXPIRES" in stripped and "RESIDUAL TIME" in stripped:
            in_table = True
            continue
        if not in_table or not stripped:
            continue

        cols = re.split(r"\s{2,}", stripped)
        if len(cols) < 3:
            continue

        name = cols[0].strip()
        date_match = _DATE_RE.search(stripped)
        if not date_match:
            continue

        try:
            expiry = datetime.strptime(date_match.group(1), _EXPIRY_FMT).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            expiry = None

        if "<invalid>" in cols[2].strip().lower():
            expiry = None

        results.append((name, expiry))

    return results


def _days_left(expiry: Optional[datetime]) -> int:
    if expiry is None:
        return -1
    return (expiry - datetime.now(timezone.utc)).days


def _severity(days: int, warn_days: int, crit_days: int) -> Severity:
    if days < 0:
        return Severity.CRITICAL
    if days <= crit_days:
        return Severity.CRITICAL
    if days <= warn_days:
        return Severity.WARNING
    return Severity.OK


def run_cert_checks(k8s_config: dict, thresholds: dict) -> List[CheckResult]:
    """
    SSH into the K8s control-plane and return one CheckResult per certificate.
    Connection path: Mac → jump_host (topology-host) → control-plane (dc01-vm-00).
    """
    warn_days = thresholds.get("cert_warning_days", 30)
    crit_days = thresholds.get("cert_critical_days", 7)

    cp = k8s_config["control_plane"]
    jump = k8s_config.get("jump_host")
    t0 = time.monotonic()

    session = SSHSession()
    try:
        session.connect(
            host=cp["ip"],
            user=cp["user"],
            password=cp["password"],
            jump_host=jump["ip"] if jump else None,
            jump_user=jump.get("user") if jump else None,
            jump_password=jump.get("password") if jump else None,
        )
    except Exception as exc:
        session.close()
        path = f"{jump['ip']} → " if jump else ""
        return [CheckResult(
            id="L5-SSH",
            name=f"SSH  {path}{cp['ip']}",
            layer=5,
            severity=Severity.ERROR,
            message=f"Connection failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )]

    try:
        raw, _, _ = session.sudo_run(
            "kubeadm certs check-expiration", password=cp["password"], timeout=30
        )
    except Exception as exc:
        return [CheckResult(
            id="L5-CERTS-CMD",
            name="kubeadm certs check-expiration",
            layer=5,
            severity=Severity.ERROR,
            message=f"Command failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )]
    finally:
        session.close()

    elapsed = int((time.monotonic() - t0) * 1000)
    entries = _parse_output(raw)

    if not entries:
        return [CheckResult(
            id="L5-CERTS-PARSE",
            name="Parse kubeadm output",
            layer=5,
            severity=Severity.ERROR,
            message="No certificate entries found — kubeadm may not be installed or output format changed",
            detail=raw,
            duration_ms=elapsed,
        )]

    results = []
    for idx, (name, expiry) in enumerate(entries):
        days = _days_left(expiry)
        sev = _severity(days, warn_days, crit_days)
        if days < 0:
            msg = "EXPIRED" if expiry is None else f"EXPIRED {-days}d ago"
        else:
            date_str = expiry.strftime("%Y-%m-%d") if expiry else "unknown"
            msg = f"Expires in {days}d  ({date_str})"
        results.append(CheckResult(
            id=f"L5-CERT-{idx:02d}",
            name=f"cert: {name}",
            layer=5,
            severity=sev,
            message=msg,
            duration_ms=elapsed if idx == len(entries) - 1 else 0,
        ))

    return results
