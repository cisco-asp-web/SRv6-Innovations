#!/bin/bash

# Start bridges
#!/usr/bin/env bash
set -euo pipefail

BRIDGES=(
  "vm-00-fe" "vm-01-fe" "vm-02-fe"
  "vm-00-be" "vm-01-be" "vm-02-be"
)

for b in "${BRIDGES[@]}"; do
  ip link add name "$b" type bridge 2>/dev/null || true
  ip link set "$b" up
done

# Start vm-00 Control Plane VM
virsh start vm-00

# Start vm-01 Worker VM
virsh start vm-01

# Start vm-02 Worker VM
virsh start vm-02