#!/bin/bash

# Start bridges
#!/usr/bin/env bash
set -euo pipefail

BRIDGES=(
  "dc01-vm-00-fe" "dc01-vm-01-fe" "dc01-vm-02-fe"
  "dc01-vm-00-be" "dc01-vm-01-be" "dc01-vm-02-be"
)

for b in "${BRIDGES[@]}"; do
  ip link add name "$b" type bridge 2>/dev/null || true
  ip link set "$b" up
done

# Start dc01-vm-00 Control Plane VM
virsh start dc01-vm-00

# Start dc01-vm-01 Worker VM
virsh start dc01-vm-01

# Start dc01-vm-02 Worker VM
virsh start dc01-vm-02