# SRv6-Innovations Lab — QA Framework

> **DRAFT — Not yet validated against a live lab.**
> All layer specifications and automation scripts are pending end-to-end testing during the next lab iteration (after June 2026).
> Do not rely on check results until this notice is removed.

---

## Table of Contents

| Section | Audience |
|---------|----------|
| [For Proctors — Pre-Session Checklist](#for-proctors--pre-session-checklist) | Instructors / TAs running the lab |
| [For Proctors — Reading Results & Fixing Failures](#for-proctors--reading-results--fixing-failures) | During a session |
| [For Students — What to Do If Something Breaks](#for-students--what-to-do-if-something-breaks) | Lab participants |
| [Automation Status](#automation-status) | Everyone |
| [Technical Reference — Layer Map & Checks](#layer-map) | Engineers / framework developers |
| [QA Framework Implementation](#qa-framework-implementation) | Engineers building the automation |

---

## For Proctors — Pre-Session Checklist

Run these steps **on the day of each lab session**, before students connect.

### Step 1 — One-time Mac setup (do this once, ever)

```bash
cd SRv6-Innovations/qa
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Step 2 — Run the full pre-flight check

From your Mac, with the dCloud session active:

```bash
cd SRv6-Innovations/qa
.venv/bin/python qa_runner.py
```

This single command checks all 9 layers in order:
- **L0** — Can we SSH to topology-host and jalapeno-host? Docker running? Images present?
- **L1** — Are the 3 KVM VMs (dc01-vm-00/01/02) running? Are bridges UP?
- **L2** — Are all 15 containers running (xrd01-07, sonic switches, app containers)? Restart counts?
- **L3** — Do all XRd routers have ISIS neighbors Up? Are SRv6 locators active? Are RR BGP sessions established?
- **L4** — Does each SONiC node have its FRR BGP sessions established?
- **L5** — Are Kubernetes certificates valid? (the cert expiry incident trigger)
- **L6** — Are TIG containers running? InfluxDB and Grafana HTTP health checks passing?
- **L7** — Are Jalapeno services up? ArangoDB API healthy? Kafka/gRPC ports open? Graph DB populated?
- **L8** — End-to-end: can app-container-01 ping app-container-07? Can VM-00 reach the WAN and fabric?

If a layer fails, downstream layers are automatically skipped.

**Sample healthy output:**

```
SRv6-Innovations Lab QA  [2026-06-08 09:15]

── L0 — Prerequisites & host reachability ──
 L0-01   SSH → 198.18.133.100     ✓ OK       Connected (312ms)
 L0-02   SSH → 198.18.128.101     ✓ OK       Connected (287ms)
 L0-03   Docker running            ✓ OK       active
 L0-04   libvirtd running          ✓ OK       active
 L0-06   Disk space /home/cisco    ✓ OK       43GB available
 L0-07   Docker image: xrd         ✓ OK       Present
 L0-08   Docker image: sonic       ✓ OK       Present

── L1 — KVM virtual machines ──
 L1-01   KVM: dc01-vm-00           ✓ OK       running
 L1-02   KVM: dc01-vm-01           ✓ OK       running
 L1-03   KVM: dc01-vm-02           ✓ OK       running
 L1-04   Network bridges UP (fe)   ✓ OK       All 3 UP
 L1-05   Network bridges UP (be)   ✓ OK       All 3 UP

── L2 — Containerlab topology & Docker ──
 L2-MGT  Docker network: mgt       ✓ OK       Subnet 172.20.6.0/24
 L2-01   container: xrd01          ✓ OK       Running (restarts: 0)
 ...
 L2-15   container: app-container-07  ✓ OK    Running (restarts: 0)

── L5 — Kubernetes certificates ──
 L5-CERT-00  cert: admin.conf      ✓ OK       Expires in 364d (2027-06-08)
 L5-CERT-01  cert: apiserver       ⚠ WARNING  Expires in 22d  (2026-06-30)
 ...

Summary: 25 OK  |  1 WARN  |  0 CRITICAL  |  0 ERROR  |  0 SKIP
```

**Status meanings:**

| Icon | Meaning | Action before session |
|------|---------|----------------------|
| `✓ OK` | Healthy | None |
| `⚠ WARNING` | Certificate expires < 30 days | Renew this week (lab works today) |
| `✗ CRITICAL` | Failed / cert expired | Fix before students connect |
| `! ERROR` | Could not reach host | Check dCloud session / VPN |
| `─ SKIP` | Not tested (upstream failed) | Fix the upstream ERROR first |

Run a single layer to investigate a specific problem:
```bash
.venv/bin/python qa_runner.py --layer 2   # containers only
.venv/bin/python qa_runner.py --layer 5   # certs only
.venv/bin/python qa_runner.py --verbose   # show raw output for failures
```

### Step 3 — If certificates need renewal

SSH to the K8s control-plane and run the renewal script:

```bash
ssh cisco@198.18.133.100               # topology-host
ssh cisco@192.168.122.100              # dc01-vm-00 (control-plane)
sudo bash /home/cisco/SRv6-Innovations/qa/remediation/renew-k8s-certs.sh
```

The script backs up existing certs, renews all of them, and restarts control-plane pods. It also tells you to restart kubelet on the two worker nodes — **don't skip that step**.

```
DONE — control-plane certificates renewed.
You must still restart kubelet on the WORKER NODES:
  ssh cisco@192.168.122.101 'sudo systemctl restart kubelet'
  ssh cisco@192.168.122.102 'sudo systemctl restart kubelet'
```

Re-run `qa_runner.py --layer 5` to confirm.

### Step 4 — End-to-end smoke test (after all checks pass)

```bash
ssh cisco@198.18.133.100
docker exec app-container-01 ping -c 3 20.0.0.1
```

All 3 pings should succeed — this confirms the WAN fabric (XRd SRv6) is forwarding traffic. If not, check [Issue Classification](#issue-classification).

---

## For Proctors — Reading Results & Fixing Failures

### Failure decision tree

```
cert check → ! ERROR
  └─ Is the dCloud session active?  NO → Start session, wait 2 min, retry
  └─ Can you ping 198.18.133.100?   NO → Check your VPN / dCloud client
  └─ Config correct?                    → Check qa/config.yaml IPs

cert check → ✗ CRITICAL (expired or < 7 days)
  └─ Run qa/remediation/renew-k8s-certs.sh on dc01-vm-00
  └─ Restart kubelet on vm-01 and vm-02
  └─ Re-run cert check to confirm

cert check → ⚠ WARNING (< 30 days)
  └─ Lab will run fine today
  └─ Schedule renewal within the week

Containers not running
  └─ docker logs <container-name>   — check for errors
  └─ Exit code 137 = OOM killed     → host needs more RAM freed
  └─ Redeploy: cd lab_X && clab deploy -t lab_X-topology.clab.yaml

K8s nodes NotReady
  └─ ssh cisco@192.168.122.100 'kubectl describe node dc01-vm-00'
  └─ Most common causes: kubelet stopped, cert expired, etcd unreachable
  └─ Try: ssh cisco@192.168.122.100 'sudo systemctl restart kubelet'

ISIS not forming on XRd
  └─ Is the container running? docker ps | grep xrd
  └─ Show config: docker exec xrd01 show running-config
  └─ Redeploy container if config is missing

Students can't reach their XRd (SSH/console)
  └─ Check management network: ping 172.20.6.101 from topology-host
  └─ Verify Containerlab topology is running: clab inspect
```

### Issue classification reference

| Symptom | Likely layer | First command to run |
|---------|-------------|----------------------|
| Can't SSH anywhere | L0 | `ping 198.18.133.100` |
| Containers exited | L2 | `docker ps -a` then `docker logs <name>` |
| ISIS not forming | L3 | `docker exec xrd01 show isis neighbors` |
| BGP stuck in Idle | L3 | Check ISIS first — BGP needs ISIS loopbacks |
| K8s nodes NotReady | L5 | `kubectl get nodes`, then check kubelet + certs |
| Pods CrashLoopBackOff | L5 | `kubectl describe pod <name> -n kube-system` |
| Cilium BGP not peering | L5+L3 | `cilium bgp peers` on vm-00, check xrd05/xrd06 |
| app01 → app07 ping failing | L8 | `traceroute` through XRd, check SRv6 SIDs |
| No data in Grafana | L6 | `docker logs lab-telegraf`, check telemetry sub on XRd |
| Jalapeno graph empty | L7 | `nc -z 198.18.128.101 32400` — gRPC port open? |

---

## For Students — What to Do If Something Breaks

The proctor validates the lab environment before each session using the automated QA tool — you do not need to verify infrastructure yourself. If something is not working during the lab, use this guide to describe the problem clearly so the proctor can fix it quickly.

### Report to your proctor

Tell them:
1. **Which lab** you are on (lab_1 through lab_5)
2. **What you were trying to do** (e.g. "SSH to xrd01", "run ping in app-container-01")
3. **The exact command** you ran
4. **The exact error** you got (copy-paste the terminal output)

That four-line report gives the proctor everything they need to fix it in minutes.

### Common things that break and who fixes them

| Symptom | Who fixes it | What they do |
|---------|-------------|--------------|
| Can't SSH to a router | Proctor | Checks container state, redeploys if needed |
| Ping between app containers fails | Proctor | Checks ISIS/BGP/SRv6 convergence |
| `kubectl` commands fail or hang | Proctor | Checks K8s certs, restarts kubelet |
| Grafana shows no data | Proctor | Checks Telegraf and telemetry subscriptions |
| Container CLI is unresponsive | Proctor | Restarts container |
| "connection refused" on lab port | Proctor | Checks service is running |

### Things students can try themselves

```bash
# My SSH session dropped — just reconnect
ssh cisco@198.18.133.100          # topology-host

# I need to get into a router again
ssh cisco@172.20.6.101            # xrd01 (adjust number for your router)

# I want to check if my ping works
docker exec app-container-01 ping -c 3 20.0.0.1

# Grafana dashboard
open http://198.18.133.100:3000   # admin / cisco123
```

If these don't work, call the proctor.

---

## Lab Environment Reference

Quick-reference for all IPs and credentials used in the lab.

| Host | IP | SSH user | Password | Role |
|------|----|----------|----------|------|
| topology-host | `198.18.133.100` | `cisco` | `cisco123` | Runs containers + KVM |
| jalapeno-host | `198.18.128.101` | `cisco` | `cisco123` | SDN controller + graph DB |
| dc01-vm-00 | `192.168.122.100` | `cisco` | `cisco123` | K8s control-plane |
| dc01-vm-01 | `192.168.122.101` | `cisco` | `cisco123` | K8s worker |
| dc01-vm-02 | `192.168.122.102` | `cisco` | `cisco123` | K8s worker |
| xrd01 | `172.20.6.101` | `cisco` | `cisco123` | IOS-XR PE router |
| xrd02 | `172.20.6.102` | `cisco` | `cisco123` | IOS-XR transit |
| xrd03 | `172.20.6.103` | `cisco` | `cisco123` | IOS-XR RR |
| xrd04 | `172.20.6.104` | `cisco` | `cisco123` | IOS-XR RR |
| xrd05 | `172.20.6.105` | `cisco` | `cisco123` | IOS-XR RR |
| xrd06 | `172.20.6.106` | `cisco` | `cisco123` | IOS-XR transit |
| xrd07 | `172.20.6.107` | `cisco` | `cisco123` | IOS-XR PE router |
| sonic-leaf-00 | `172.20.6.128` | `cisco` | `cisco123` | SONiC leaf switch |
| sonic-leaf-01 | `172.20.6.129` | `cisco` | `cisco123` | SONiC leaf switch |
| sonic-leaf-02 | `172.20.6.130` | `cisco` | `cisco123` | SONiC leaf switch |
| sonic-spine-00 | `172.20.6.192` | `cisco` | `cisco123` | SONiC spine switch |
| sonic-spine-01 | `172.20.6.193` | `cisco` | `cisco123` | SONiC spine switch |
| sonic-spine-02 | `172.20.6.194` | `cisco` | `cisco123` | SONiC spine switch |
| Grafana | `198.18.133.100:3000` | `admin` | `cisco123` | Telemetry dashboard |
| InfluxDB | `198.18.133.100:8086` | `admin` | `cisco123` | Time-series DB |
| ArangoDB | `198.18.128.101:8529` | — | — | Jalapeno graph DB |

---

## Automation Status

Current state of `qa/qa_runner.py` — what is actually coded vs what is designed in the spec below.

| Layer | Domain | Automated | Script/module |
|-------|--------|-----------|---------------|
| L0 | Host reachability, Docker, libvirtd, disk, images | ✅ Yes | `checks/layer0_prereqs.py` |
| L1 | KVM VMs (virsh state), network bridges | ✅ Yes | `checks/layer1_kvm.py` |
| L2 | All 15 Docker containers, mgt-network | ✅ Yes | `checks/layer2_containerlab.py` |
| L3 | XRd — ISIS adjacency, BGP sessions (RRs), SRv6 locators | ✅ Yes | `checks/layer3_xrd.py` |
| L4 | SONiC — FRR running, BGP sessions via vtysh | ✅ Yes | `checks/layer4_sonic.py` |
| L5 | K8s certificates (kubeadm certs check-expiration) | ✅ Yes | `checks/layer5_kubernetes.py` |
| L6 | TIG stack — containers, InfluxDB/Grafana HTTP health | ✅ Yes | `checks/layer6_tig.py` |
| L7 | Jalapeno — ArangoDB API, Kafka/gRPC ports, graph collections | ✅ Yes | `checks/layer7_jalapeno.py` |
| L8 | End-to-end WAN pings, VM frontend/backend reachability | ✅ Yes | `checks/layer8_e2e.py` |

All 9 layers run in a single `qa_runner.py` invocation with automatic layer gating. A failure at L0 skips all downstream layers. Routing layers (L3/L4) gate on L2 (containers must be running). L8 gates on L3 + L4 + L5 (routing and K8s must be healthy before end-to-end tests).

**Note for L7 — Jalapeno containers:** The `containers` list in `config.yaml` under `jalapeno:` is intentionally empty by default because container names vary by deployment. Populate it by running:
```bash
ssh cisco@198.18.128.101 'docker ps --format "{{.Names}}"'
```

---

> Everything below this line is the **engineering reference** for the QA framework itself —
> layer-by-layer check specifications, implementation architecture, and development notes.
> Proctors and students do not need to read further.

---

This document defines the quality assurance framework for the SRv6-Innovations lab environment. It covers **what** should be validated before and during any lab session and **how** to automate those validations.

---

## Lab Architecture Summary (QA Scope)

```
┌──────────────────────────────────────────────────────────────────┐
│  dCloud Environment (Cisco internal cloud)                       │
│                                                                  │
│  ┌──────────────────────┐  ┌───────────────────────────────┐    │
│  │  Topology Host       │  │  Jalapeno Host                │    │
│  │  198.18.133.100      │  │  198.18.128.101               │    │
│  │                      │  │                               │    │
│  │  ┌──────────────┐    │  │  ArangoDB (graph DB)          │    │
│  │  │ Containerlab │    │  │  Kafka (event bus)            │    │
│  │  │  ─ xrd01-07  │    │  │  InfluxDB (time-series)       │    │
│  │  │  ─ 6x SONiC  │    │  │  gRPC :32400 (telemetry in)  │    │
│  │  │  ─ 2x apps   │    │  └───────────────────────────────┘    │
│  │  └──────────────┘    │                                        │
│  │                      │                                        │
│  │  ┌──────────────┐    │                                        │
│  │  │   KVM / libvirt    │                                        │
│  │  │  dc01-vm-00  │────┼── K8s control-plane (10.8.0.2)         │
│  │  │  dc01-vm-01  │────┼── K8s worker       (10.8.1.2)         │
│  │  │  dc01-vm-02  │────┼── K8s worker       (10.8.2.2)         │
│  │  └──────────────┘    │                                        │
│  │                      │                                        │
│  │  ┌──────────────┐    │                                        │
│  │  │  TIG Stack   │    │                                        │
│  │  │  Telegraf    │    │                                        │
│  │  │  InfluxDB    │    │                                        │
│  │  │  Grafana :3000    │                                        │
│  │  └──────────────┘    │                                        │
│  └──────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────┘
```

The validation stack has **8 layers**, ordered from infrastructure up to end-to-end application behavior. A failure at a lower layer invalidates all checks above it.

---

## Layer Map

| Layer | Domain | Owner host | Critical |
|-------|--------|------------|----------|
| L0 | Prerequisites & host reachability | External → dCloud | Yes |
| L1 | KVM virtual machines | topology-host | Yes |
| L2 | Containerlab topology & Docker | topology-host | Yes |
| L3 | XRd routing protocols (ISIS / BGP / SRv6) | topology-host | Yes |
| L4 | SONiC DC fabric (BGP / FRR) | topology-host | Yes |
| L5 | Kubernetes cluster & certificates | dc01-vm-00/01/02 | Yes |
| L6 | Observability stack (TIG) | topology-host | No |
| L7 | Jalapeno SDN stack | jalapeno-host | No |
| L8 | End-to-end data-plane tests | all | Yes |

---

## Layer 0 — Prerequisites & Host Reachability

**Goal:** Confirm the dCloud VMs are alive and dependencies are installed before touching anything else.

### Checks

| ID | Check | Method | Pass criterion |
|----|-------|--------|----------------|
| L0-01 | topology-host ICMP reachability | `ping -c 3 198.18.133.100` | 0% packet loss |
| L0-02 | jalapeno-host ICMP reachability | `ping -c 3 198.18.128.101` | 0% packet loss |
| L0-03 | topology-host SSH | `ssh cisco@198.18.133.100 echo ok` | Connection accepted, exit 0 |
| L0-04 | jalapeno-host SSH | `ssh cisco@198.18.128.101 echo ok` | Connection accepted, exit 0 |
| L0-05 | Docker engine running on topology-host | `systemctl is-active docker` | `active` |
| L0-06 | Docker engine running on jalapeno-host | `systemctl is-active docker` | `active` |
| L0-07 | Containerlab binary present | `clab version` | Version string returned |
| L0-08 | virsh / libvirt running | `systemctl is-active libvirtd` | `active` |
| L0-09 | Free disk space on topology-host | `df -h /home/cisco` | > 20 GB free |
| L0-10 | Free disk space on jalapeno-host | `df -h /home/cisco` | > 10 GB free |
| L0-11 | Available RAM on topology-host | `free -g` | > 8 GB free |
| L0-12 | NTP / clock sync | `timedatectl show --property=NTPSynchronized` | `yes` |
| L0-13 | XRd Docker image present | `docker image inspect cisco-xrd-control-plane:24.4.1` | Exit 0 |
| L0-14 | SONiC Docker image present | `docker image inspect vrnetlab/sonic_sonic-vs:vpp20250422` | Exit 0 |

### Why these matter
- Missing Docker images cause silent containerlab failures (containers stay in `Exited` state).
- Clock skew > 5 seconds breaks TLS handshakes, Kafka, and Kubernetes certificate validation.

---

## Layer 1 — KVM Virtual Machines

**Goal:** The three nested VMs that form the Kubernetes cluster must be defined in libvirt and running.

### Checks

| ID | Check | Method | Pass criterion |
|----|-------|--------|----------------|
| L1-01 | dc01-vm-00 defined in virsh | `virsh dominfo dc01-vm-00` | Exit 0 |
| L1-02 | dc01-vm-01 defined in virsh | `virsh dominfo dc01-vm-01` | Exit 0 |
| L1-03 | dc01-vm-02 defined in virsh | `virsh dominfo dc01-vm-02` | Exit 0 |
| L1-04 | dc01-vm-00 running | `virsh domstate dc01-vm-00` | `running` |
| L1-05 | dc01-vm-01 running | `virsh domstate dc01-vm-01` | `running` |
| L1-06 | dc01-vm-02 running | `virsh domstate dc01-vm-02` | `running` |
| L1-07 | Frontend bridges UP | `ip link show dc01-vm-00-fe dc01-vm-01-fe dc01-vm-02-fe` | State `UP` for all |
| L1-08 | Backend bridges UP | `ip link show dc01-vm-00-be dc01-vm-01-be dc01-vm-02-be` | State `UP` for all |
| L1-09 | VM-00 SSH reachable | `ssh cisco@192.168.122.100 echo ok` | Exit 0 |
| L1-10 | VM-01 SSH reachable | `ssh cisco@192.168.122.101 echo ok` | Exit 0 |
| L1-11 | VM-02 SSH reachable | `ssh cisco@192.168.122.102 echo ok` | Exit 0 |
| L1-12 | VM-00 frontend interface UP | `ip link show ens4` (on vm-00) | State `UP`, addr `10.8.0.2/24` |
| L1-13 | VM-00 backend interface UP | `ip link show ens5` (on vm-00) | State `UP`, addr `fcbb:0:0800:0::2/64` |
| L1-14 | VM-0x frontend route to XRd | `ip route get 10.0.0.1` (on each VM) | Route via `10.8.x.1` |

### Common failure modes
- Bridges not created because `bridges.sh` was not run after a host reboot.
- VMs in `shut off` state after dCloud session resume.
- ens4/ens5 netplan not applied (needs `netplan apply`).

---

## Layer 2 — Containerlab Topology & Docker

**Goal:** The containerlab topology must be fully deployed, all containers Running, no restarts.

### Checks

| ID | Check | Method | Pass criterion |
|----|-------|--------|----------------|
| L2-01 | Lab topology deployed | `clab inspect -t <topology>.clab.yaml` | Exit 0, topology listed |
| L2-02 | mgt-network Docker network exists | `docker network inspect mgt-network` | `Subnet: 172.20.6.0/24` |
| L2-03 | xrd01 container running | `docker inspect xrd01 --format='{{.State.Status}}'` | `running` |
| L2-04 | xrd02 container running | (same pattern) | `running` |
| L2-05 | xrd03 container running | | `running` |
| L2-06 | xrd04 container running | | `running` |
| L2-07 | xrd05 container running | | `running` |
| L2-08 | xrd06 container running | | `running` |
| L2-09 | xrd07 container running | | `running` |
| L2-10 | sonic-leaf-00 container running | `docker inspect sonic-leaf-00 --format='{{.State.Status}}'` | `running` |
| L2-11 | sonic-leaf-01 running | | `running` |
| L2-12 | sonic-leaf-02 running | | `running` |
| L2-13 | sonic-spine-00 running | | `running` |
| L2-14 | sonic-spine-01 running | | `running` |
| L2-15 | sonic-spine-02 running | | `running` |
| L2-16 | app-container-01 running | `docker inspect app-container-01 --format='{{.State.Status}}'` | `running` |
| L2-17 | app-container-07 running | | `running` |
| L2-18 | No containers with high restart count | `docker ps --format='{{.Names}} {{.Status}}'` | No `Restarting` or `Restart > 3` |
| L2-19 | XRd01 management IP reachable | `ping -c 2 172.20.6.101` | 0% packet loss |
| L2-20 | All XRd mgmt IPs reachable | Ping 172.20.6.101-107 | All respond |
| L2-21 | SONiC mgmt IPs reachable | Ping 172.20.6.128-130, .192-.194 | All respond |

### Tip
Use `docker ps -a --filter name=xrd` for a fast bulk status. A container in `Exited` with code `137` means OOM-killed — check host RAM.

---

## Layer 3 — XRd Routing Protocols (ISIS / BGP / SRv6)

**Goal:** All control-plane adjacencies must be established, SRv6 locators active, and routing tables complete.

SSH to each XRd via management IP (172.20.6.101-107), credentials `cisco/cisco123`.

### ISIS

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L3-01 | xrd01 ISIS neighbors | `show isis neighbors` | ≥ 2 neighbors in `Up` state |
| L3-02 | xrd02 ISIS neighbors | same | ≥ 2 neighbors Up |
| L3-03 | xrd03 ISIS neighbors | same | ≥ 2 neighbors Up |
| L3-04 | xrd04 ISIS neighbors | same | ≥ 2 neighbors Up |
| L3-05 | xrd05 ISIS neighbors | same | ≥ 2 neighbors Up |
| L3-06 | xrd06 ISIS neighbors | same | ≥ 2 neighbors Up |
| L3-07 | xrd07 ISIS neighbors | same | ≥ 2 neighbors Up |
| L3-08 | ISIS LSDB completeness | `show isis database` | 7 LSPs in DB on all routers |
| L3-09 | ISIS BGP-LS redistribution | `show isis database detail` | Link-state attributes advertised |

### BGP

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L3-10 | xrd01 BGP sessions | `show bgp summary` | Sessions to xrd05, xrd06 in `Estab` |
| L3-11 | xrd02 BGP sessions | same | Estab to RRs |
| L3-12 | xrd07 BGP sessions | same | Estab to RRs |
| L3-13 | xrd05 (RR) BGP session count | `show bgp summary` | 5 iBGP sessions Established |
| L3-14 | xrd06 (RR) BGP session count | same | 5 iBGP sessions Established |
| L3-15 | VPNv4 table non-empty | `show bgp vpnv4 unicast` | Prefixes present |
| L3-16 | VPNv6 table non-empty | `show bgp vpnv6 unicast` | Prefixes present |
| L3-17 | BGP-LS table populated | `show bgp link-state link-state summary` | Link-state entries present |

### SRv6

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L3-18 | xrd01 SRv6 locator active | `show segment-routing srv6 locators` | `xtc_srv6` locator in `Active` state |
| L3-19 | SRv6 locator xrd01 | same | Prefix `fc00:0:1111::/48` |
| L3-20 | SRv6 locator xrd02 | same (on xrd02) | `fc00:0:2222::/48` |
| L3-21 | SRv6 locator xrd03 | | `fc00:0:3333::/48` |
| L3-22 | SRv6 locator xrd04 | | `fc00:0:4444::/48` |
| L3-23 | SRv6 locator xrd05 | | `fc00:0:5555::/48` |
| L3-24 | SRv6 locator xrd06 | | `fc00:0:6666::/48` |
| L3-25 | SRv6 locator xrd07 | | `fc00:0:7777::/48` |
| L3-26 | SRv6 SID table populated | `show segment-routing srv6 sid` | SIDs present per router |
| L3-27 | Remote SRv6 locators in IPv6 RIB | `show route ipv6` | fc00:0:XXXX::/48 for all peers |
| L3-28 | SRv6 uSID reachability | `ping fc00:0:1111::1 count 5` (from xrd07) | 5/5 success |

### Telemetry

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L3-29 | gRPC destination reachable | `show grpc` | Connected to 198.18.128.101:32400 |
| L3-30 | Telemetry subscription active | `show telemetry model-driven subscription base_metrics` | State: Active |

---

## Layer 4 — SONiC DC Fabric

**Goal:** SONiC BGP sessions between leaves and spines must be Established, loopbacks reachable.

SSH to SONiC nodes (172.20.6.128-130, 172.20.6.192-194), credentials `cisco/cisco123`.

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L4-01 | FRR running on leaf-00 | `sudo systemctl status frr` | Active/running |
| L4-02 | FRR running on all SONiC nodes | same | Active on all 6 |
| L4-03 | leaf-00 BGP sessions | `show bgp summary` | 3 sessions Established (to 3 spines) |
| L4-04 | leaf-01 BGP sessions | same | 3 sessions Established |
| L4-05 | leaf-02 BGP sessions | same | 3 sessions Established |
| L4-06 | spine-00 BGP sessions | same | 3 sessions Established (to 3 leaves) |
| L4-07 | spine-01 BGP sessions | same | 3 sessions Established |
| L4-08 | spine-02 BGP sessions | same | 3 sessions Established |
| L4-09 | leaf-00 loopback reachable | `ping fcbb:0:0800::1 -c 3` from VM-00 | 3/3 |
| L4-10 | leaf-01 loopback reachable | `ping fcbb:0:0801::1 -c 3` | 3/3 |
| L4-11 | leaf-02 loopback reachable | `ping fcbb:0:0802::1 -c 3` | 3/3 |
| L4-12 | ECMP paths on leaf-00 | `show ip route` | ≥ 2 ECMP paths to spines |
| L4-13 | SONiC interfaces UP | `show interfaces status` | eth1-eth3 UP per node |

---

## Layer 5 — Kubernetes Cluster & Certificates

**Goal:** All nodes Ready, system pods healthy, and — critically — no certificate is expired or expiring within 30 days.

Run from `dc01-vm-00` (control plane) at `192.168.122.100`.

### Cluster health

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L5-01 | K8s API server reachable | `kubectl cluster-info` | API server URL returned |
| L5-02 | All nodes Ready | `kubectl get nodes` | All 3 nodes in `Ready` state |
| L5-03 | dc01-vm-00 Ready | `kubectl get node dc01-vm-00 -o jsonpath='{.status.conditions[-1].type}'` | `Ready` |
| L5-04 | dc01-vm-01 Ready | same | `Ready` |
| L5-05 | dc01-vm-02 Ready | same | `Ready` |
| L5-06 | No nodes NotReady | `kubectl get nodes --no-headers | grep -v Ready` | Empty output |

### Certificate expiry — top priority

This is the incident category that triggered this QA initiative. A Kubernetes cluster with expired certificates becomes completely unreachable.

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L5-07 | **kubeadm cert expiry report** | `kubeadm certs check-expiration` | All certs valid, none expiring < 30d |
| L5-08 | apiserver cert validity | Parse output of L5-07 | Expires > today + 30d |
| L5-09 | apiserver-etcd-client cert | same | Expires > today + 30d |
| L5-10 | apiserver-kubelet-client cert | same | Expires > today + 30d |
| L5-11 | front-proxy-ca cert | same | Expires > today + 30d |
| L5-12 | etcd-healthcheck-client cert | same | Expires > today + 30d |
| L5-13 | Kubelet serving cert | `openssl x509 -in /var/lib/kubelet/pki/kubelet.crt -noout -enddate` | Not before today + 30d |
| L5-14 | kubeconfig cert (admin) | `openssl x509 -in /etc/kubernetes/admin.conf ... -noout -enddate` | Not before today + 30d |

**Severity thresholds:**
- `CRITICAL` — cert expires in < 7 days or already expired
- `WARNING` — cert expires in 7–30 days
- `OK` — cert expires in > 30 days

**Remediation script** (see `qa/remediation/renew-k8s-certs.sh`):
```bash
# Renew all kubeadm-managed certificates
kubeadm certs renew all
# Restart control-plane components to pick up new certs
kubectl -n kube-system rollout restart deployment/coredns
systemctl restart kubelet
```

### System pods

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L5-15 | kube-system pods healthy | `kubectl get pods -n kube-system` | All Running or Completed, 0 CrashLoopBackOff |
| L5-16 | etcd pod running | `kubectl get pod -n kube-system -l component=etcd` | 1/1 Running |
| L5-17 | kube-apiserver pod running | same with `component=kube-apiserver` | 1/1 Running |
| L5-18 | kube-scheduler pod running | | 1/1 Running |
| L5-19 | kube-controller-manager running | | 1/1 Running |
| L5-20 | CoreDNS running | `kubectl get pods -n kube-system -l k8s-app=kube-dns` | 2/2 Running |

### Cilium CNI

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L5-21 | Cilium pods running | `kubectl get pods -n kube-system -l k8s-app=cilium` | 3/3 Running (one per node) |
| L5-22 | Cilium operator running | `kubectl get pods -n kube-system -l name=cilium-operator` | Running |
| L5-23 | Cilium status | `cilium status` | All components OK |
| L5-24 | Cilium connectivity test | `cilium connectivity test` | All tests passed |
| L5-25 | BGP peers established (vm-00) | `cilium bgp peers` (on vm-00) | 2 peers `Established` (xrd05, xrd06) |
| L5-26 | BGP peers established (vm-01) | same | 2 peers Established |
| L5-27 | BGP peers established (vm-02) | same | 2 peers Established |
| L5-28 | SRv6 locator pool defined | `kubectl get isovalentsrv6locatorpool` | Resource exists, pool not empty |
| L5-29 | SRv6 carrots VRF defined | `kubectl get isovalentsrv6egressgatewaygroup` | carrots VRF present |

### Multus

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L5-30 | Multus pods running | `kubectl get pods -n kube-system -l app=multus` | DaemonSet pods all Running |
| L5-31 | NetworkAttachmentDefinition CRD exists | `kubectl get crd networkattachmentdefinitions.k8s.cni.cncf.io` | CRD found |

### Scheduling validation

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L5-32 | Pod can be scheduled on vm-00 | Deploy `qa/manifests/test-pod.yaml` with `nodeSelector` | Pod reaches Running state |
| L5-33 | Pod can be scheduled on vm-01 | same | Running |
| L5-34 | Pod can be scheduled on vm-02 | same | Running |

---

## Layer 6 — Observability Stack (TIG)

**Goal:** Telegraf, InfluxDB, and Grafana are running and telemetry data is flowing.

Run from topology-host or check exposed ports from management workstation.

| ID | Check | Method | Pass criterion |
|----|-------|--------|----------------|
| L6-01 | lab-influxdb container running | `docker inspect lab-influxdb --format='{{.State.Status}}'` | `running` |
| L6-02 | lab-telegraf container running | same | `running` |
| L6-03 | lab-grafana container running | same | `running` |
| L6-04 | lab-mysql container running | same | `running` |
| L6-05 | InfluxDB HTTP API responding | `curl -s http://172.20.6.200:8086/health` | `{"status":"pass"}` |
| L6-06 | Grafana HTTP responding | `curl -s -o /dev/null -w '%{http_code}' http://172.20.6.202:3000` | `200` |
| L6-07 | InfluxDB has recent data | `influx query 'from(bucket:"telemetry-bucket") |> range(start:-5m) |> count()'` | Row count > 0 |
| L6-08 | gNMI measurements in InfluxDB | Query for `openconfig_interfaces` measurement | Data within last 15 min |
| L6-09 | SRv6 SID measurements present | Query for `srv6-sid` measurement | Data within last 5 min |

---

## Layer 7 — Jalapeno SDN Stack

**Goal:** Jalapeno services on the jalapeno host (198.18.128.101) are up and the graph database contains topology data.

| ID | Check | Method | Pass criterion |
|----|-------|--------|----------------|
| L7-01 | Jalapeno containers running | `docker ps` on jalapeno-host | All Jalapeno service containers `Up` |
| L7-02 | ArangoDB HTTP API | `curl -s http://198.18.128.101:8529/_api/version` | Returns version JSON |
| L7-03 | Kafka broker reachable | `nc -z 198.18.128.101 9092` | Connection accepted |
| L7-04 | gRPC telemetry port open | `nc -z 198.18.128.101 32400` | Connection accepted |
| L7-05 | Graph DB has node entries | ArangoDB API query on `ls_node` collection | Count > 0 |
| L7-06 | Graph DB has link entries | ArangoDB API query on `ls_link` collection | Count > 0 |
| L7-07 | Graph DB has SRv6 SID entries | ArangoDB API query on `srv6_sid` collection | Count > 0 |
| L7-08 | Jalapeno API responding | `curl -s http://198.18.128.101:8080/api/v1/topology` | 200 OK |

---

## Layer 8 — End-to-End Data Plane Tests

**Goal:** Prove traffic actually flows through the intended paths in the data plane. These are the highest-value tests because they catch mismatches between control-plane state and actual forwarding behavior.

### WAN connectivity (XRd network)

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L8-01 | app-container-01 → app-container-07 IPv4 | `docker exec app-container-01 ping -c 5 20.0.0.1` | 5/5 success |
| L8-02 | app-container-01 → app-container-07 IPv6 | `docker exec app-container-01 ping6 -c 5 fc00:0:40::1` | 5/5 success |
| L8-03 | app-container-07 → app-container-01 IPv4 | reverse ping | 5/5 success |
| L8-04 | xrd01 CE reachability | `ping 10.101.1.2 vrf default` from xrd01 | 5/5 |
| L8-05 | xrd07 CE reachability | `ping 10.107.1.2 vrf default` from xrd07 | 5/5 |
| L8-06 | VRF carrots CE-CE | `ping vrf carrots 10.107.1.2 source 10.101.1.2` from xrd01 | 5/5 success |
| L8-07 | SRv6 traceroute path xrd01→xrd07 | `traceroute fc00:0:7777::1 source fc00:0:1111::1` | Passes through expected SIDs |
| L8-08 | ECMP load distribution | Send 100 flows, check `show interfaces counters` | Traffic spread across both paths |

### Kubernetes ↔ WAN connectivity

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L8-09 | VM-00 frontend → xrd01 | `ping 10.8.0.1 -c 5` from vm-00 | 5/5 |
| L8-10 | VM-00 → xrd01 loopback | `ping 10.0.0.1 -c 5` from vm-00 | 5/5 |
| L8-11 | VM-00 → xrd07 loopback IPv6 | `ping6 fc00:0:7777::1 -c 5` from vm-00 | 5/5 |
| L8-12 | K8s pod → XRd reachability | Deploy test pod, `kubectl exec -- ping 10.0.0.1` | 5/5 |
| L8-13 | Cilium BGP routes visible on xrd05 | `show bgp ipv6 unicast` on xrd05 | K8s pod CIDR present |

### SONiC fabric connectivity

| ID | Check | Command | Pass criterion |
|----|-------|---------|----------------|
| L8-14 | VM-00 backend → leaf-00 | `ping6 fcbb:0:0800::1 -c 5` from vm-00 ens5 | 5/5 |
| L8-15 | VM-01 backend → leaf-01 | `ping6 fcbb:0:0801::1 -c 5` from vm-01 ens5 | 5/5 |
| L8-16 | VM-02 backend → leaf-02 | `ping6 fcbb:0:0802::1 -c 5` from vm-02 ens5 | 5/5 |
| L8-17 | Cross-leaf reachability | `ping6 fcbb:0:0801::1` from vm-00 (leaf-00 side) | 5/5 via spine |

---

## QA Framework Implementation

### Proposed Architecture

```
qa/
├── qa_runner.py              # Main orchestrator — entry point
├── config.yaml               # Lab inventory: IPs, credentials, thresholds
├── checks/
│   ├── base.py               # CheckResult dataclass, severity enum, base class
│   ├── layer0_prereqs.py
│   ├── layer1_kvm.py
│   ├── layer2_containerlab.py
│   ├── layer3_xrd.py         # Uses netmiko for IOS-XR SSH
│   ├── layer4_sonic.py       # Uses netmiko for SONiC SSH
│   ├── layer5_kubernetes.py  # Uses kubernetes Python client + subprocess kubeadm
│   ├── layer6_tig.py
│   ├── layer7_jalapeno.py
│   └── layer8_e2e.py
├── reporters/
│   ├── console.py            # Rich terminal table output
│   ├── json_reporter.py      # Machine-readable output for CI/CD
│   └── html_reporter.py      # Human-readable HTML dashboard
└── remediation/
    ├── renew-k8s-certs.sh    # Cert renewal script (the emergency procedure)
    └── restart-containers.sh # Container restart helpers
```

### Core Data Model

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Severity(Enum):
    OK      = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    SKIP    = "SKIP"      # upstream layer failed, test meaningless

@dataclass
class CheckResult:
    id: str
    name: str
    layer: int
    severity: Severity
    message: str
    detail: Optional[str] = None   # raw command output or traceback
    duration_ms: int = 0
```

### config.yaml structure

```yaml
lab:
  name: "SRv6-Innovations"
  active_topology: "lab_1"  # lab_1 through lab_5

hosts:
  topology_host:
    ip: "198.18.133.100"
    user: "cisco"
    password: "cisco123"
  jalapeno_host:
    ip: "198.18.128.101"
    user: "cisco"
    password: "cisco123"
  k8s_vms:
    - ip: "192.168.122.100"  # vm-00 / control-plane
      user: "cisco"
      password: "cisco123"
    - ip: "192.168.122.101"
      user: "cisco"
      password: "cisco123"
    - ip: "192.168.122.102"
      user: "cisco"
      password: "cisco123"

xrd_nodes:
  xrd01: { mgmt_ip: "172.20.6.101", loopback_v4: "10.0.0.1", locator: "fc00:0:1111::/48" }
  xrd02: { mgmt_ip: "172.20.6.102", loopback_v4: "10.0.0.2", locator: "fc00:0:2222::/48" }
  xrd03: { mgmt_ip: "172.20.6.103", loopback_v4: "10.0.0.3", locator: "fc00:0:3333::/48" }
  xrd04: { mgmt_ip: "172.20.6.104", loopback_v4: "10.0.0.4", locator: "fc00:0:4444::/48" }
  xrd05: { mgmt_ip: "172.20.6.105", loopback_v4: "10.0.0.5", locator: "fc00:0:5555::/48", role: rr }
  xrd06: { mgmt_ip: "172.20.6.106", loopback_v4: "10.0.0.6", locator: "fc00:0:6666::/48", role: rr }
  xrd07: { mgmt_ip: "172.20.6.107", loopback_v4: "10.0.0.7", locator: "fc00:0:7777::/48" }

sonic_nodes:
  sonic-leaf-00:  { mgmt_ip: "172.20.6.128", loopback_v6: "fcbb:0:0800::1" }
  sonic-leaf-01:  { mgmt_ip: "172.20.6.129", loopback_v6: "fcbb:0:0801::1" }
  sonic-leaf-02:  { mgmt_ip: "172.20.6.130", loopback_v6: "fcbb:0:0802::1" }
  sonic-spine-00: { mgmt_ip: "172.20.6.192" }
  sonic-spine-01: { mgmt_ip: "172.20.6.193" }
  sonic-spine-02: { mgmt_ip: "172.20.6.194" }

thresholds:
  cert_warning_days: 30
  cert_critical_days: 7
  min_disk_gb: 20
  min_ram_gb: 8
  max_container_restarts: 3
  ping_loss_pct_max: 0
```

### Invocation CLI

```bash
# Full pre-flight check before a lab session
python qa/qa_runner.py --config qa/config.yaml --mode preflight

# Quick check — layers 0-2 only (fast, ~30s)
python qa/qa_runner.py --mode quick

# Certificate-only check (can be run daily via cron)
python qa/qa_runner.py --module layer5_kubernetes --check certs

# Specific layer
python qa/qa_runner.py --layer 3

# JSON output for CI/CD integration
python qa/qa_runner.py --format json --output qa-report.json

# HTML dashboard output
python qa/qa_runner.py --format html --output qa-report.html

# Watch mode (reruns every N seconds)
python qa/qa_runner.py --mode watch --interval 300
```

### Console Output Example

```
┌─────────────────────────────────────────────────────────────────┐
│  SRv6-Innovations Lab QA Report — 2026-06-08 14:32:01          │
│  Mode: preflight | Lab: lab_1                                   │
├──────┬──────────────────────────────────┬──────────┬───────────┤
│  ID  │  Check                           │  Status  │  Detail   │
├──────┼──────────────────────────────────┼──────────┼───────────┤
│ L0-01│ topology-host ICMP              │  ✓ OK    │  3ms RTT  │
│ L0-08│ libvirtd running                │  ✓ OK    │           │
│ L1-04│ dc01-vm-00 running              │  ✓ OK    │           │
│ L5-07│ K8s cert expiry                 │ ⚠ WARN  │ 22d left  │ ← generated alert last incident
│ L5-08│ apiserver cert                  │ ⚠ WARN  │ 22d left  │
│ L3-01│ xrd01 ISIS neighbors            │  ✓ OK    │  2 Up     │
│ L8-01│ app01 → app07 IPv4 ping         │  ✓ OK    │  0% loss  │
└──────┴──────────────────────────────────┴──────────┴───────────┘
Summary: 47 OK  |  2 WARN  |  0 CRITICAL  |  0 SKIP
Duration: 1m 43s
```

### Python Dependencies

```
# qa/requirements.txt
paramiko>=3.0          # SSH to Linux hosts and KVM
netmiko>=4.0           # SSH + CLI parsing for XRd (cisco_xr driver) and SONiC (linux driver)
kubernetes>=28.0       # K8s API client
cryptography>=42.0     # Parse X.509 certs for expiry checking without openssl subprocess
docker>=7.0            # Docker SDK for container state checks
requests>=2.31         # HTTP health checks (InfluxDB, Grafana, ArangoDB)
pyyaml>=6.0            # config.yaml parsing
rich>=13.0             # Terminal output formatting
jinja2>=3.0            # HTML report rendering
click>=8.0             # CLI argument parsing
```

### Key Implementation Notes

**Certificate check (L5-07 to L5-14)**

The most critical check given the incident history. Use `kubeadm certs check-expiration` for kubeadm-managed certs, and parse X.509 directly for kubelet and kubeconfig certs:

```python
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timezone

def check_cert_expiry(cert_pem: bytes, warning_days=30, critical_days=7) -> CheckResult:
    cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
    expires = cert.not_valid_after_utc
    days_left = (expires - datetime.now(timezone.utc)).days
    if days_left < 0:
        return CRITICAL, f"EXPIRED {-days_left} days ago"
    if days_left < critical_days:
        return CRITICAL, f"Expires in {days_left} days"
    if days_left < warning_days:
        return WARNING, f"Expires in {days_left} days"
    return OK, f"Expires in {days_left} days"
```

**Parallel execution**

Checks within the same layer that hit different hosts can run concurrently. Use `asyncio` or `concurrent.futures.ThreadPoolExecutor` with a pool sized to the number of remote hosts (~10 threads):

```python
with ThreadPoolExecutor(max_workers=10) as pool:
    futures = {pool.submit(check.run): check for check in layer_checks}
    results = [f.result() for f in futures]
```

**Layer gating**

If L0 (host reachability) fails, skip L1-L8 and mark them `SKIP` — there is no point SSHing into routers if the VMs are unreachable. Each layer gate condition is defined in the runner:

```python
LAYER_GATES = {
    1: lambda results: all_ok(results, layer=0),
    2: lambda results: all_ok(results, layer=0),
    3: lambda results: all_ok(results, layer=2),   # containers must be up
    5: lambda results: all_ok(results, layer=1),   # VMs must be up
    8: lambda results: all_ok(results, layer=[3, 4, 5]),
}
```

**XRd CLI parsing with netmiko**

```python
from netmiko import ConnectHandler

xr_device = {
    "device_type": "cisco_xr",
    "host": "172.20.6.101",
    "username": "cisco",
    "password": "cisco123",
}
with ConnectHandler(**xr_device) as conn:
    output = conn.send_command("show isis neighbors")
    # Parse "Up" count with regex
```

**SONiC CLI parsing**

SONiC exposes standard Linux + FRR CLI. Use `device_type: linux` for the host shell and `device_type: linux` or a custom prompt pattern for `vtysh`:

```python
conn.send_command("sudo vtysh -c 'show bgp summary'")
```

---

## Remediation Scripts

### renew-k8s-certs.sh

This is the emergency procedure that was needed during the incident. Keep it here as a first-class artifact:

```bash
#!/usr/bin/env bash
# Renew all kubeadm-managed K8s certificates.
# Must be run as root on dc01-vm-00 (control-plane node).
# After running: restart kubelet on all nodes and re-copy admin.conf.

set -euo pipefail

echo "=== Backing up existing certs ==="
cp -r /etc/kubernetes/pki /etc/kubernetes/pki.bak.$(date +%Y%m%d_%H%M%S)
cp /etc/kubernetes/admin.conf /etc/kubernetes/admin.conf.bak.$(date +%Y%m%d_%H%M%S)

echo "=== Renewing all kubeadm certificates ==="
kubeadm certs renew all

echo "=== Restarting control-plane pods (they read certs at startup) ==="
# Control-plane static pods auto-restart when manifests are touched:
for manifest in /etc/kubernetes/manifests/*.yaml; do
  touch "$manifest"
done

sleep 20  # wait for pods to cycle

echo "=== Restarting kubelet on control-plane ==="
systemctl restart kubelet

echo "=== Copying new admin.conf to ~/.kube/config ==="
cp /etc/kubernetes/admin.conf ~/.kube/config
chown "$(id -u):$(id -g)" ~/.kube/config

echo "=== Verifying new certificate expiry ==="
kubeadm certs check-expiration

echo ""
echo "NOTE: You must also restart kubelet on WORKER nodes (dc01-vm-01, dc01-vm-02)"
echo "  ssh cisco@192.168.122.101 'sudo systemctl restart kubelet'"
echo "  ssh cisco@192.168.122.102 'sudo systemctl restart kubelet'"
```

---

## Recommended QA Workflow

### Before every lab session (pre-flight, ~2 min)

```
1. python qa/qa_runner.py --mode quick          # L0 + L1 + L2 only, fast
2. python qa/qa_runner.py --layer 5 --check certs  # cert check always
```

If quick passes → proceed to full:
```
3. python qa/qa_runner.py --mode preflight      # all layers
```

### Nightly (scheduled via cron on topology-host)

```bash
# /etc/cron.d/lab-qa
0 3 * * * cisco cd /home/cisco/SRv6-Innovations && python qa/qa_runner.py \
    --mode preflight --format json --output /tmp/qa-report-$(date +\%Y\%m\%d).json 2>&1 \
    | mail -s "Lab QA Report $(date +\%Y-\%m-\%d)" lab-team@example.com
```

### Certificate monitoring (daily, mandatory)

```bash
# /etc/cron.d/k8s-cert-check
0 8 * * * cisco python /home/cisco/SRv6-Innovations/qa/qa_runner.py \
    --module layer5_kubernetes --check certs \
    --alert-on WARNING   # alert when 30 days left, not just 7
```

### Post-incident (after any topology restart)

Run full pre-flight + end-to-end:
```
python qa/qa_runner.py --mode full --format html --output /tmp/postincident-$(date +%Y%m%d).html
```

---

## Issue Classification

| Symptom | Likely layer | First check |
|---------|-------------|-------------|
| Can't SSH anywhere | L0 | VPN/dCloud session active? |
| Containers exited | L2 | `docker logs <container>`, OOM? |
| ISIS not forming | L3 | Container running? MTU mismatch? |
| BGP stuck in Idle | L3 | ISIS converged first? Loopback reachable? |
| K8s nodes NotReady | L5 | kubelet running? certs expired? etcd healthy? |
| Pods CrashLoopBackOff | L5 | `kubectl describe pod`, image pull? resource limit? |
| Cilium BGP not peering | L5+L3 | xrd05/xrd06 reachable from VM frontend? BGP session on XRd? |
| Ping app01→app07 failing | L8 | Trace each layer: container→xrd01→WAN→xrd07→container |
| No data in Grafana | L6 | Telegraf connected to InfluxDB? XRd telemetry sub active? |
| Jalapeno graph empty | L7 | gRPC port 32400 open? XRd telemetry destination reachable? |

---

## Future Extensions

- **Ansible integration**: wrap each layer's checks as Ansible tasks using `assert` module so the same inventory can drive both deployment and validation.
- **Prometheus exporter**: expose QA check results as Prometheus metrics so Grafana can show lab health over time alongside routing telemetry.
- **Lab-specific profiles**: `--lab lab_3` runs only checks relevant to the Cilium/K8s lab (L5 gets heavier weight, SONiC L4 checks can be skipped if not yet configured).
- **Student pod isolation**: when multiple student pods share the same dCloud session, parameterize the checks by pod number so each pod can self-validate independently.
- **Automated remediation hooks**: for certain well-understood failures (cert expiry, bridge missing, container OOM-restart), the runner can optionally trigger the remediation script automatically with a `--remediate` flag.
