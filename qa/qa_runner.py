#!/usr/bin/env python3
"""
SRv6-Innovations Lab QA Runner

Automated pre-flight check for the lab environment.
Runs layers in order; skips a layer if its dependency failed.

Usage:
  python qa_runner.py                   # full pre-flight, uses qa/config.yaml
  python qa_runner.py --config path.yaml
  python qa_runner.py --format json     # machine-readable output
  python qa_runner.py --verbose         # show raw output on failures
  python qa_runner.py --layer 5         # run a single layer only

Layers implemented:
  L0  Host reachability & prerequisites  (topology-host, jalapeno-host)
  L1  KVM virtual machines               (virsh state, network bridges)
  L2  Containerlab topology              (Docker containers, mgt-network)
  L3  XRd routing protocols             (ISIS adjacency, BGP sessions, SRv6 locators)
  L4  SONiC DC fabric                   (FRR BGP sessions via vtysh)
  L5  Kubernetes certificates            (kubeadm certs check-expiration)
  L6  Observability stack               (TIG containers, InfluxDB/Grafana HTTP)
  L7  Jalapeno SDN stack                (ArangoDB, Kafka, gRPC, graph collections)
  L8  End-to-end data plane             (WAN pings, VM frontend/backend reachability)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from checks.base import CheckResult, Severity
from checks.layer0_prereqs import run_prereq_checks
from checks.layer1_kvm import run_kvm_checks
from checks.layer2_containerlab import run_container_checks
from checks.layer3_xrd import run_xrd_checks
from checks.layer4_sonic import run_sonic_checks
from checks.layer5_kubernetes import run_cert_checks
from checks.layer6_tig import run_tig_checks
from checks.layer7_jalapeno import run_jalapeno_checks
from checks.layer8_e2e import run_e2e_checks

# ── Optional rich output ──────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.rule import Rule
    from rich.table import Table

    _console = Console()
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

_ICON = {
    Severity.OK:       "✓",
    Severity.WARNING:  "⚠",
    Severity.CRITICAL: "✗",
    Severity.ERROR:    "!",
    Severity.SKIP:     "─",
}
_COLOR = {
    Severity.OK:       "green",
    Severity.WARNING:  "yellow",
    Severity.CRITICAL: "red",
    Severity.ERROR:    "red",
    Severity.SKIP:     "dim",
}
_LAYER_NAMES = {
    0: "L0 — Prerequisites & host reachability",
    1: "L1 — KVM virtual machines",
    2: "L2 — Containerlab topology & Docker",
    3: "L3 — XRd routing protocols (ISIS / BGP / SRv6)",
    4: "L4 — SONiC DC fabric (FRR / BGP)",
    5: "L5 — Kubernetes certificates",
    6: "L6 — Observability stack (TIG)",
    7: "L7 — Jalapeno SDN stack",
    8: "L8 — End-to-end data plane",
}


# ── Layer gating ──────────────────────────────────────────────────────────────

def _layer_failed(results: List[CheckResult], layer: int) -> bool:
    """True if the layer has any CRITICAL or ERROR result."""
    return any(
        r.layer == layer and r.severity in (Severity.CRITICAL, Severity.ERROR)
        for r in results
    )


def _layer_blocked(results: List[CheckResult], layer: int) -> bool:
    """True if the layer failed or was itself skipped (upstream failure)."""
    return any(
        r.layer == layer and r.severity in (Severity.CRITICAL, Severity.ERROR, Severity.SKIP)
        for r in results
    )


def _skip(layer: int, reason: str) -> List[CheckResult]:
    return [CheckResult(
        id=f"L{layer}-SKIP",
        name=f"Layer {layer} — skipped",
        layer=layer,
        severity=Severity.SKIP,
        message=reason,
    )]


# ── Output helpers ────────────────────────────────────────────────────────────

def _print_rich(results: List[CheckResult], title: str, verbose: bool) -> None:
    _console.print(f"\n[bold]{title}[/bold]\n")
    by_layer: Dict[int, List[CheckResult]] = {}
    for r in results:
        by_layer.setdefault(r.layer, []).append(r)

    for layer_num in sorted(by_layer):
        _console.print(Rule(_LAYER_NAMES.get(layer_num, f"Layer {layer_num}"), style="dim"))
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("ID",     style="dim", width=18)
        table.add_column("Check",  min_width=38)
        table.add_column("Status", width=12)
        table.add_column("Detail")
        for r in by_layer[layer_num]:
            c = _COLOR[r.severity]
            icon = _ICON[r.severity]
            detail = r.message
            if verbose and r.detail:
                detail += f"\n[dim]{r.detail[:300]}[/dim]"
            table.add_row(r.id, r.name, f"[{c}]{icon} {r.severity.value}[/{c}]", detail)
        _console.print(table)


def _print_plain(results: List[CheckResult], title: str, verbose: bool) -> None:
    print(f"\n{title}\n")
    by_layer: Dict[int, List[CheckResult]] = {}
    for r in results:
        by_layer.setdefault(r.layer, []).append(r)

    for layer_num in sorted(by_layer):
        print(f"\n── {_LAYER_NAMES.get(layer_num, f'Layer {layer_num}')} ──")
        print(f"{'ID':<20} {'Check':<40} {'Status':<10} Detail")
        print("-" * 96)
        for r in by_layer[layer_num]:
            icon = _ICON[r.severity]
            print(f"{r.id:<20} {r.name:<40} {icon} {r.severity.value:<8} {r.message}")
            if verbose and r.detail:
                for line in r.detail[:300].splitlines():
                    print(f"{'':20}   {line}")


def _print_summary(results: List[CheckResult]) -> None:
    counts = {s: 0 for s in Severity}
    for r in results:
        counts[r.severity] += 1
    parts = [
        f"{counts[Severity.OK]} OK",
        f"{counts[Severity.WARNING]} WARN",
        f"{counts[Severity.CRITICAL]} CRITICAL",
        f"{counts[Severity.ERROR]} ERROR",
        f"{counts[Severity.SKIP]} SKIP",
    ]
    print("\nSummary: " + "  |  ".join(parts))

    if counts[Severity.ERROR] > 0 and counts[Severity.CRITICAL] == 0:
        print(
            "\nCONNECTIVITY ERROR: Could not reach one or more lab hosts.\n"
            "  • Is the dCloud session active?\n"
            "  • Can you ping 198.18.133.100 (topology-host)?\n"
            "  • Check qa/config.yaml for correct IPs and credentials."
        )
    elif counts[Severity.CRITICAL] > 0:
        print(
            "\nACTION REQUIRED: One or more critical checks failed.\n"
            "  If certificates are expired: run qa/remediation/renew-k8s-certs.sh\n"
            "  If containers are down: check docker logs <name> on topology-host\n"
            "  If VMs are down: run virsh start <vm> or check infrastructure/vms/\n"
            "  If ISIS/BGP is down: check container state, then routing config"
        )
    elif counts[Severity.WARNING] > 0:
        print(
            "\nWARNING: Review the items above before the lab session."
        )
    else:
        print("\nAll checks passed — lab is ready.")


# ── Config & runner ───────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def results_to_json(results: List[CheckResult]) -> str:
    return json.dumps([
        {
            "id": r.id,
            "name": r.name,
            "layer": r.layer,
            "severity": r.severity.value,
            "message": r.message,
            "detail": r.detail,
            "duration_ms": r.duration_ms,
        }
        for r in results
    ], indent=2)


def run_all(cfg: dict, only_layer: Optional[int] = None) -> List[CheckResult]:
    """Execute all implemented layers with gating. Returns all results."""
    results: List[CheckResult] = []
    hosts = cfg.get("hosts", {})
    thresholds = cfg.get("thresholds", {})

    def _should_run(layer: int) -> bool:
        return only_layer is None or only_layer == layer

    # ── L0 — Prerequisites ────────────────────────────────────────────────────
    if _should_run(0):
        results += run_prereq_checks(
            hosts_config=hosts,
            thresholds=thresholds,
            docker_images=cfg.get("docker_images", []),
        )

    # ── L1 — KVM VMs  (gate: L0 topology-host SSH must pass) ─────────────────
    if _should_run(1):
        if only_layer is None and _layer_failed(results, 0):
            results += _skip(1, "L0 topology-host unreachable")
        else:
            results += run_kvm_checks(hosts_config=hosts)

    # ── L2 — Containers  (gate: same as L1) ──────────────────────────────────
    if _should_run(2):
        if only_layer is None and _layer_failed(results, 0):
            results += _skip(2, "L0 topology-host unreachable")
        else:
            results += run_container_checks(
                hosts_config=hosts,
                containers=cfg.get("containers", []),
                thresholds=thresholds,
            )

    # ── L3 — XRd protocols  (gate: L2 containers must be running) ────────────
    if _should_run(3):
        if only_layer is None and _layer_blocked(results, 2):
            results += _skip(3, "L2 containers not running or L0 unreachable")
        else:
            results += run_xrd_checks(
                hosts_config=hosts,
                xrd_nodes=cfg.get("xrd_nodes", []),
            )

    # ── L4 — SONiC fabric  (gate: L2 containers must be running) ─────────────
    if _should_run(4):
        if only_layer is None and _layer_blocked(results, 2):
            results += _skip(4, "L2 containers not running or L0 unreachable")
        else:
            results += run_sonic_checks(
                hosts_config=hosts,
                sonic_nodes=cfg.get("sonic_nodes", []),
            )

    # ── L5 — K8s certificates  (gate: L0 reachable + L1 VMs up) ─────────────
    if _should_run(5):
        if only_layer is None and (_layer_blocked(results, 0) or _layer_blocked(results, 1)):
            results += _skip(5, "topology-host unreachable or KVM VMs not running")
        else:
            results += run_cert_checks(
                k8s_config=cfg["kubernetes"],
                thresholds=thresholds,
            )

    # ── L6 — TIG stack  (gate: L2 containers must be running) ────────────────
    if _should_run(6):
        if only_layer is None and _layer_blocked(results, 2):
            results += _skip(6, "L2 containers not running or L0 unreachable")
        else:
            results += run_tig_checks(
                hosts_config=hosts,
                tig_config=cfg.get("tig", {}),
            )

    # ── L7 — Jalapeno  (gate: L0 jalapeno-host reachable) ────────────────────
    if _should_run(7):
        if only_layer is None and _layer_failed(results, 0):
            results += _skip(7, "L0 jalapeno-host unreachable")
        else:
            results += run_jalapeno_checks(
                hosts_config=hosts,
                jalapeno_config=cfg.get("jalapeno", {}),
            )

    # ── L8 — End-to-end  (gate: L3 + L4 + L5 not blocked) ───────────────────
    if _should_run(8):
        if only_layer is None and (
            _layer_blocked(results, 3)
            or _layer_blocked(results, 4)
            or _layer_blocked(results, 5)
        ):
            results += _skip(8, "Routing (L3/L4) or K8s (L5) not ready")
        else:
            results += run_e2e_checks(
                hosts_config=hosts,
                e2e_config=cfg.get("e2e", {}),
            )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SRv6-Innovations Lab QA — pre-flight checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml (default: qa/config.yaml)",
    )
    parser.add_argument(
        "--format", choices=["console", "json"], default="console",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show raw command output for failed checks",
    )
    parser.add_argument(
        "--layer", type=int, metavar="N",
        help="Run only layer N (0–8)",
    )
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 2
    except yaml.YAMLError as exc:
        print(f"ERROR: bad YAML in config: {exc}", file=sys.stderr)
        return 2

    results = run_all(cfg, only_layer=args.layer)

    if args.format == "json":
        print(results_to_json(results))
    else:
        title = f"SRv6-Innovations Lab QA  [{datetime.now().strftime('%Y-%m-%d %H:%M')}]"
        if _HAS_RICH:
            _print_rich(results, title, args.verbose)
        else:
            _print_plain(results, title, args.verbose)
        _print_summary(results)

    counts = {s: 0 for s in Severity}
    for r in results:
        counts[r.severity] += 1
    return 1 if (counts[Severity.CRITICAL] > 0 or counts[Severity.ERROR] > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
