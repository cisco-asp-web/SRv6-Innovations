# SRv6-Innovations: Improvement TODO

---

## Initiative #0: Generic Topology Cleanup (Rename City-Based Names) ✅ COMPLETE

> **Value:** The current topology uses European city names (london, amsterdam, berlin, zurich, paris, barcelona, rome) throughout every layer of the lab — router configs, VM definitions, container directories, Ansible playbooks, Kubernetes manifests, and all documentation. This creates two problems: it implies a specific geographic narrative that may not resonate with every audience, and it makes the lab harder to reuse or adapt for other events. Renaming to neutral numbered identifiers (xrd01–xrd07, vm-00–vm-02, etc.) makes the topology generic, professional, and immediately reusable as a base for any future lab or customer demonstration.

### Renaming Map (applied)

| Old Name             | New Name            | Role                  |
|----------------------|---------------------|-----------------------|
| xrd-london           | xrd01               | PE / Edge             |
| xrd-amsterdam        | xrd02               | P / Transit           |
| xrd-berlin           | xrd03               | P / Transit           |
| xrd-zurich           | xrd04               | P / Transit           |
| xrd-paris            | xrd05               | Route Reflector       |
| xrd-barcelona        | xrd06               | Route Reflector       |
| xrd-rome             | xrd07               | PE / Edge             |
| app-container-london | app-container-01    | Edge host (xrd01 side)|
| app-container-rome   | app-container-07    | Edge host (xrd07 side)|
| london-vm-00         | vm-00               | K8s control plane     |
| london-vm-01         | vm-01               | K8s worker            |
| london-vm-02         | vm-02               | K8s worker            |

> SONiC nodes (sonic-leaf-00/01/02, sonic-spine-00/01/02) were already generic — no change needed.

### Completed Changes

#### Containerlab Topology Files
- [x] `lab_1/lab_1-topology.clab.yaml` — node names, startup-config paths, bridge names, link endpoints, exec hostname blocks, comments
- [x] `lab_2/lab_2-topology.clab.yaml`
- [x] `lab_3/lab_3-topology.clab.yaml`
- [x] `lab_4/lab_4-topology.clab.yaml`
- [x] `lab_5/lab_5-topology.clab.yaml` — did not exist, skipped

#### XRd Router Configs (renamed + updated)
- [x] `lab_1/xrd-config/` — all 7 files renamed (london→xrd01, amsterdam→xrd02, berlin→xrd03, zurich→xrd04, paris→xrd05, barcelona→xrd06, rome→xrd07)
- [x] `lab_2/xrd-config/` — same 7 files renamed
- [x] `lab_3/xrd-config/` — same 7 files renamed
- [x] Hostnames, interface descriptions, BGP neighbor descriptions updated in all `.cfg` files
- [x] `lab_1/xrd-config/lab_1_quick_config.md`
- [x] `lab_2/xrd-config/lab_2_quick_config.md`

#### Lab Guides (documentation)
- [x] `lab_1/lab_1-guide.md`
- [x] `lab_2/lab_2-guide.md`
- [x] `lab_2/lab_2-packet-walk.md`
- [x] `lab_2/validation-cmd-output.md`
- [x] `lab_3/lab_3-guide.md`
- [x] `lab_3/lab_3-appendix.md`
- [x] `lab_3/k8s-install-instructions.md`
- [x] `lab_3/cilium/reference.md`
- [x] `lab_4/lab_4-guide.md`
- [x] `lab_4/lab_4-appendix.md`
- [x] `lab_4/sonic_cli_reference.md`
- [x] `lab_5/lab_5-guide.md`
- [x] `lab_5/lab_5-bonus.md`
- [x] `lab_5/lab_5-notes.md`
- [x] `lab_5/jalapeno/example-api-calls.md`
- [x] `lab_5/jalapeno/example-arango-queries.md`
- [x] `README.md` (root)

#### Cilium / Kubernetes Manifests
- [x] `lab_3/cilium/01-cilium-bgp.yaml` — nodeSelector and NodeConfigOverride names
- [x] `lab_3/cilium/02-cilium-srv6.yaml` — no changes needed
- [x] `lab_3/cilium/03-carrots-vrf.yaml` — nodeName updated
- [x] `lab_3/cilium/98-test-egress-policy.yaml` — no changes needed
- [x] `lab_3/cilium/99-cilium-all.yaml` — all node refs updated
- [x] `lab_5/srv6-pytorch/srv6-pytorch-test.yaml` — nodeName and comments updated

#### Ansible Playbooks
- [x] `london_vms_base_playbook.yaml` → renamed to `vms_base_playbook.yaml`
- [x] `london_vms_k8s_install.yaml` → renamed to `vms_k8s_install.yaml`
- [x] `london_vms_k8s_workers.yaml` → renamed to `vms_k8s_workers.yaml`
- [x] `infrastructure/ansible/hosts` — group names updated (`london_vms`→`k8s_vms`, `london_k8s_cp`→`k8s_cp`, etc.)
- [x] `infrastructure/ansible/startup_playbook.yaml`
- [x] `infrastructure/ansible/cleanup_playbook.yaml`
- [x] `infrastructure/ansible/files/vm_virsh.yaml`

#### Infrastructure — VM Definitions
- [x] `london-bridges.sh` → `bridges.sh`
- [x] `london-bridges.service` → `bridges.service`
- [x] `london-vm-00/` → `vm-00/` — directory + all 5 files inside renamed and updated
- [x] `london-vm-01/` → `vm-01/` — directory + all 5 files inside renamed and updated
- [x] `london-vm-02/` → `vm-02/` — directory + all 5 files inside renamed and updated
- [x] `vm-00/k8s/multus-test.yaml` and `test-host-srv6-pod.yaml` — nodeName fields updated

#### Infrastructure — Containers
- [x] `infrastructure/containers/london/` → `app-container-01/`
  - [x] `london-network-fix.sh` → `network-fix.sh`
  - [x] `entrypoint.sh`, `Dockerfile`, `README.md` updated
- [x] `infrastructure/containers/rome/` → `app-container-07/`
  - [x] `rome-network-fix.sh` → `network-fix.sh`
  - [x] `entrypoint.sh`, `Dockerfile`, `README.md` updated

#### Cleanup & Latency Scripts
- [x] `lab_1/add-latency.sh` — all clab node name references updated
- [x] `lab_1/cleanup-lab_1.sh` — no city refs found, no changes needed
- [x] `lab_2/cleanup-lab_2.sh` — no city refs found, no changes needed

#### Jalapeno Python Scripts
- [x] `lab_5/jalapeno/frontend/get_nodes.py`
- [x] `lab_5/jalapeno/frontend/add_meta_data.py`
- [x] `lab_5/jalapeno/frontend/set_latency.py`
- [x] `lab_5/jalapeno/frontend/set_latency_ipv6.py`
- [x] `lab_5/jalapeno/backend/add-data.py`
- [x] `lab_5/jalapeno/backend/clear-load.py`

#### Topology Drawings (images)
- [x] 10 city-named PNG files in `topo_drawings/` renamed to xrdNN equivalents
- [x] 4 active image references in lab guides updated to match new filenames

#### xarchive/
- [x] `xarchive/debug-pods.yaml` — nodeName fields updated
- [x] `xarchive/berlin-history.md` — london-vm-00 references updated; filename kept as-is (historical shell log)

---

## Initiative #1: Topology Visualization Webapp

> **Value:** Currently, participants interact with the lab exclusively through CLI — SSH into routers, run show commands, and mentally map the output to a topology they have to remember. There is no live visual feedback. A web-based topology viewer with traffic generation buttons would dramatically improve the learning experience: participants can see the network as a graph, watch SRv6 paths light up in real-time, and trigger traffic flows with a single click instead of writing commands. For demo and sales engineering contexts, this transforms the lab into a compelling, self-service showcase that any audience can engage with — no networking background required to appreciate what is happening on screen.

### 1.1 Backend (FastAPI)
- [ ] Scaffold FastAPI project under `webapp/backend/`
- [ ] SSH exec helper (Paramiko) — run show commands on XRd/SONiC nodes
- [ ] `GET /api/topology` — static node/link graph parsed from containerlab YAML files
- [ ] `GET /api/topology/state` — live ISIS/BGP adjacency state per node
- [ ] `GET /api/paths` — proxy to Jalapeno REST API (shortest-path, next-best-path)
- [ ] `POST /api/traffic/generate` — trigger iperf3/ping flows via SSH exec
- [ ] WebSocket `/ws/topology` — push live updates (link state, SID counters, utilization)
- [ ] Dockerfile for backend container

### 1.2 Frontend (React + Cytoscape.js)
- [ ] Scaffold React app under `webapp/frontend/`
- [ ] Render full topology graph: xrd01–xrd07 + 6 SONiC nodes + 3 VMs + 2 app containers
- [ ] Color edges by latency (green / yellow / red)
- [ ] Click node → side panel: loopback IPs, SRv6 locator, ISIS/BGP state
- [ ] Click link → panel: latency (ms), utilization (%), MTU
- [ ] Lab switcher dropdown (Lab 1–5) — highlight relevant nodes, fade others
- [ ] Traffic generation buttons:
  - [ ] Ping bulk path → xrd01→xrd02→xrd03→xrd04→xrd07
  - [ ] Ping low-latency path → xrd01→xrd05→xrd04→xrd07
  - [ ] iperf3 bulk flow (color-10 policy)
  - [ ] iperf3 low-latency flow (color-20 policy)
  - [ ] Dual-path comparison (both simultaneously)
  - [ ] Trigger PyTorch job (Lab 5)
  - [ ] Toggle ECMP mode (Lab 5)
- [ ] Active flow overlay — animate active path on graph while traffic runs
- [ ] SRv6 uSID animator — show destination address shifting hop-by-hop
- [ ] Dockerfile for frontend container (nginx)

### 1.3 Deployment
- [ ] `webapp/docker-compose.yml` — wire backend + frontend together
- [ ] Expose on topology-host port 8080 (HTTP)
- [ ] Add webapp startup instructions to each lab guide

---

## Initiative #2: Telemetry Stack (Telegraf + InfluxDB + Grafana)

> **Value:** The labs already generate rich telemetry — XRd sends gRPC MDT to Jalapeno and SONiC exposes gNMI — but none of it is visualized anywhere. Participants currently have no way to see metrics trending over time or compare states before and after a configuration change. Adding a pre-configured TIG stack (Telegraf + InfluxDB + Grafana) with purpose-built dashboards per lab closes this gap entirely. It also makes the "so what" of Lab 5 (intelligent load balancing) immediately obvious: instead of reading CLI output, participants can watch a Grafana panel show training job latency drop when SRv6 steering replaces random ECMP. For Cisco, shipping pre-built dashboards alongside the lab positions SRv6 as an observable, manageable technology — not just a packet-forwarding curiosity.

### 2.1 Infrastructure
- [ ] `telemetry/docker-compose.yml` — InfluxDB 2.7, Telegraf 1.30, Grafana 10.x
- [ ] Pre-configure InfluxDB org/bucket/token via env vars
- [ ] Pre-provision Grafana datasource (InfluxDB) via provisioning YAML
- [ ] `telemetry/start.sh` and `telemetry/stop.sh`

### 2.2 Telegraf Inputs
- [ ] gRPC MDT input for XRd — SRv6 SID counters, interface stats, BGP state
- [ ] gNMI input for each SONiC node — interface counters, BGP neighbor state
- [ ] HTTP input — scrape Jalapeno REST API for graph/path metrics (Lab 5)
- [ ] Exec input — parse PyTorch training logs for allreduce/iteration timing (Lab 5)
- [ ] Prometheus input — scrape Cilium Hubble endpoint (Lab 3)

### 2.3 Grafana Dashboards
- [ ] **Dashboard 1 — WAN Core (XRd):** interface counters, SRv6 SID hits, ISIS events, BGP prefix counts, link latency heatmap
- [ ] **Dashboard 2 — SONiC DC Fabric:** per-port utilization heatmap, ECMP distribution, BGP neighbor state, packet drops
- [ ] **Dashboard 3 — Kubernetes + Cilium:** Hubble flow metrics, SRv6 SID pool utilization, pod throughput, BGP peer state
- [ ] **Dashboard 4 — Jalapeno SDN:** graph DB metrics, path computation rate, active flows with path taken, link utilization over time
- [ ] **Dashboard 5 — ECMP vs SRv6 Steering:** side-by-side collision rate, per-spine utilization variance, PyTorch allreduce latency, training iteration time, path decision log
- [ ] Pre-provision all dashboards as JSON files under `telemetry/grafana/dashboards/`

---

## Initiative #3: Per-Lab Polish & Automation

> **Value:** Each lab currently relies on participants manually running many CLI commands to validate their work, with no programmatic feedback on whether a step succeeded or failed. In a time-boxed hands-on session, this creates frustration — a misconfigured neighbor or a missed step can derail a participant for 10 minutes without them knowing why. Adding per-lab validation scripts, improving traffic generation tooling, and surfacing existing observability features (Hubble, Jalapeno CLI) reduces friction significantly. These improvements also make the labs more suitable as self-paced learning material beyond the original event context.

### Lab 1
- [ ] `lab_1/validate_lab1.sh` — run all expected show commands, print PASS/FAIL per check
- [ ] Update `add-latency.sh` to accept arguments: `./add-latency.sh <nodeA> <nodeB> <delay_ms>`
- [ ] Add `labels` metadata to `lab_1-topology.clab.yaml` for webapp node rendering

### Lab 2
- [ ] Replace `ping` validation steps with `iperf3` flows for real throughput metrics
- [ ] `lab_2/dual-path-traffic.sh` — launch both color-10 and color-20 iperf3 flows simultaneously
- [ ] `lab_2/validate_lab2.sh` — verify VRF, L3VPN prefixes, TE policy state

### Lab 3
- [ ] Add `cilium hubble enable` step and port-forward instructions to lab guide
- [ ] `lab_3/validate_lab3.sh` — verify Cilium BGP peers + pod-to-pod ping in VRF
- [ ] Add SRv6 SID pool panel to webapp (vm-00/01/02 → SID mapping)

### Lab 4
- [ ] Refactor Ansible playbook to use `community.network.sonic_*` modules where available
- [ ] Add gNMI config for each SONiC node targeting Telegraf (prerequisite for Dashboard 2)
- [ ] `lab_4/validate_lab4.sh` — check BGP sessions, SRv6 local SIDs, port states

### Lab 5
- [ ] `lab_5/jalapeno_paths.py` — CLI tool: query shortest/next-best path, print colored ASCII path result
- [ ] Add PyTorch metrics callback: write `allreduce_time_ms` and `iteration_time_ms` to InfluxDB
- [ ] Log each Jalapeno API call (src, dst, metric, path) to InfluxDB for Dashboard 4
- [ ] `lab_5/validate_lab5.sh` — verify Jalapeno reachability, ArangoDB populated, pod SRv6 routes

---

## Priority Order

| # | Item | Effort | Demo Impact |
|---|------|--------|-------------|
| ~~0~~ | ~~Rename all city references to numbered IDs~~ | ~~M~~ | ~~High~~ ✅ |
| 1 | FastAPI backend + topology API | M | High |
| 2 | React + Cytoscape.js topology graph | M | Very High |
| 3 | Traffic generation buttons (iperf3/ping) | S | High |
| 4 | TIG docker-compose + InfluxDB + Grafana base | S | High |
| 5 | Telegraf gNMI (SONiC) → Dashboard 2 | M | High |
| 6 | Telegraf gRPC MDT (XRd) → Dashboard 1 | M | High |
| 7 | SRv6 uSID path animator in webapp | L | Very High |
| 8 | Lab 5 ECMP toggle + Dashboard 5 | M | Very High |
| 9 | PyTorch metrics exporter → Dashboard 5 | M | High |
| 10 | Cilium Hubble + Dashboard 3 | S | Medium |
| 11 | Per-lab validate_labN.sh scripts | S | Medium |
| 12 | Jalapeno path CLI tool | S | Medium |
| 13 | Dashboard 4 (Jalapeno SDN) | M | Medium |

Effort: S = Small (<1 day), M = Medium (1–3 days), L = Large (3+ days)

---

## Target File Structure

```
SRv6-Innovations/
├── lab_1/
│   ├── xrd-config/
│   │   ├── xrd01.cfg, xrd02.cfg, xrd03.cfg, xrd04.cfg
│   │   ├── xrd05.cfg, xrd06.cfg, xrd07.cfg
│   │   └── lab_1_quick_config.md
│   ├── lab_1-topology.clab.yaml
│   ├── lab_1-guide.md
│   ├── add-latency.sh
│   ├── validate_lab1.sh
│   └── cleanup-lab_1.sh
├── lab_2/  (same pattern + dual-path-traffic.sh)
├── lab_3/  (same pattern + validate script)
├── lab_4/  (same pattern + validate script)
├── lab_5/  (same pattern + jalapeno_paths.py + validate script)
├── infrastructure/
│   ├── ansible/
│   │   ├── vms_base_playbook.yaml
│   │   ├── vms_k8s_install.yaml
│   │   ├── vms_k8s_workers.yaml
│   │   ├── startup_playbook.yaml
│   │   ├── cleanup_playbook.yaml
│   │   └── hosts
│   ├── containers/
│   │   ├── app-container-01/
│   │   └── app-container-07/
│   └── vms/
│       ├── bridges.sh
│       ├── bridges.service
│       ├── vm-00/, vm-01/, vm-02/
├── webapp/
│   ├── backend/
│   │   ├── main.py
│   │   ├── ssh_client.py
│   │   ├── topology.py
│   │   ├── jalapeno.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── App.jsx
│   │   │   ├── TopologyGraph.jsx
│   │   │   ├── TrafficPanel.jsx
│   │   │   ├── NodeDetails.jsx
│   │   │   └── LabSwitcher.jsx
│   │   ├── package.json
│   │   └── Dockerfile
│   └── docker-compose.yml
├── telemetry/
│   ├── docker-compose.yml
│   ├── telegraf/telegraf.conf
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/influxdb.yaml
│   │   │   └── dashboards/dashboards.yaml
│   │   └── dashboards/
│   │       ├── 01-wan-core.json
│   │       ├── 02-sonic-fabric.json
│   │       ├── 03-kubernetes-cilium.json
│   │       ├── 04-jalapeno-sdn.json
│   │       └── 05-ecmp-vs-srv6.json
│   ├── start.sh
│   └── stop.sh
└── todo.md
```
