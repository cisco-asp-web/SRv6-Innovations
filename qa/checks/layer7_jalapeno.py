"""
Layer 7 — Jalapeno SDN stack.

SSH to jalapeno-host and validate:
  - Docker containers listed in config are running
  - ArangoDB HTTP API is healthy
  - Kafka broker port is open
  - gRPC telemetry ingress port is open
  - ArangoDB graph collections (ls_node, ls_link) are populated

Checks:
  L7-{n}       Each configured Jalapeno container Running
  L7-ARANGO    ArangoDB /health API returns HTTP 200
  L7-KAFKA     Kafka port (default 9092) accepting connections
  L7-GRPC      gRPC telemetry port (default 32400) accepting connections
  L7-GRAPH     ls_node and ls_link collections non-empty
"""

import json
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
        return CheckResult(id=check_id, name=label, layer=7, severity=Severity.CRITICAL,
                           message="Not found — Jalapeno stack may not be deployed")
    if out.strip() == "running":
        return CheckResult(id=check_id, name=label, layer=7, severity=Severity.OK,
                           message="Running")
    return CheckResult(id=check_id, name=label, layer=7, severity=Severity.CRITICAL,
                       message=f"Status: {out.strip()}")


def _port_check(session: SSHSession, check_id: str, label: str, host: str, port: int) -> CheckResult:
    out, _, code = session.run(
        f"nc -z -w 3 {host} {port} && echo open || echo closed", timeout=10
    )
    if "open" in out:
        return CheckResult(id=check_id, name=label, layer=7, severity=Severity.OK,
                           message=f"Port {port} accepting connections")
    return CheckResult(id=check_id, name=label, layer=7, severity=Severity.CRITICAL,
                       message=f"Port {port} not reachable — service may be down")


def _arango_health(session: SSHSession, arango_url: str) -> CheckResult:
    label = f"ArangoDB health ({arango_url})"
    out, _, code = session.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' --connect-timeout 5 {arango_url}/_api/version",
        timeout=15,
    )
    if code != 0 or not out:
        return CheckResult(id="L7-ARANGO", name=label, layer=7, severity=Severity.CRITICAL,
                           message="curl failed — ArangoDB unreachable")
    if out.strip() == "200":
        return CheckResult(id="L7-ARANGO", name=label, layer=7, severity=Severity.OK,
                           message="HTTP 200 — API healthy")
    return CheckResult(id="L7-ARANGO", name=label, layer=7, severity=Severity.CRITICAL,
                       message=f"HTTP {out.strip()} (expected 200)")


def _graph_check(session: SSHSession, arango_url: str, collection: str, check_id: str) -> CheckResult:
    label = f"ArangoDB collection: {collection}"
    query = json.dumps({"query": f"RETURN LENGTH({collection})"})
    out, _, code = session.run(
        f"curl -s -X POST --connect-timeout 5 "
        f"-H 'Content-Type: application/json' "
        f"-d '{query}' "
        f"{arango_url}/_db/jalapeno/_api/cursor",
        timeout=15,
    )
    if code != 0 or not out:
        return CheckResult(id=check_id, name=label, layer=7, severity=Severity.ERROR,
                           message="ArangoDB query failed")
    try:
        data = json.loads(out)
        count = data.get("result", [None])[0]
    except (json.JSONDecodeError, IndexError):
        return CheckResult(id=check_id, name=label, layer=7, severity=Severity.ERROR,
                           message="Could not parse ArangoDB response", detail=out[:300])
    if count is None:
        return CheckResult(id=check_id, name=label, layer=7, severity=Severity.ERROR,
                           message="Unexpected response format", detail=out[:300])
    if count == 0:
        return CheckResult(id=check_id, name=label, layer=7, severity=Severity.WARNING,
                           message=f"Collection empty — topology data not yet ingested")
    return CheckResult(id=check_id, name=label, layer=7, severity=Severity.OK,
                       message=f"{count} entries")


def run_jalapeno_checks(hosts_config: dict, jalapeno_config: dict) -> List[CheckResult]:
    """SSH to jalapeno-host and validate Jalapeno SDN services."""
    if not jalapeno_config:
        return []

    jal = hosts_config.get("jalapeno_host")
    if not jal:
        return []

    t0 = time.monotonic()
    session = SSHSession()
    try:
        session.connect(host=jal["ip"], user=jal["user"], password=jal["password"])
    except Exception as exc:
        return [CheckResult(
            id="L7-SSH", name=f"SSH → jalapeno-host ({jal['ip']})",
            layer=7, severity=Severity.ERROR,
            message=f"Connection failed: {exc}",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )]

    results: List[CheckResult] = []
    with session:
        containers = jalapeno_config.get("containers", [])
        for idx, name in enumerate(containers, start=1):
            results.append(_container_check(session, f"L7-{idx:02d}", name))

        arango_url = jalapeno_config.get("arango_url", "")
        if arango_url:
            results.append(_arango_health(session, arango_url))
            results.append(_graph_check(session, arango_url, "ls_node", "L7-GRAPH-NODE"))
            results.append(_graph_check(session, arango_url, "ls_link", "L7-GRAPH-LINK"))

        kafka_port = jalapeno_config.get("kafka_port", 9092)
        results.append(_port_check(session, "L7-KAFKA", f"Kafka (port {kafka_port})",
                                   "localhost", kafka_port))

        grpc_port = jalapeno_config.get("grpc_port", 32400)
        results.append(_port_check(session, "L7-GRPC", f"gRPC telemetry (port {grpc_port})",
                                   "localhost", grpc_port))

    return results
