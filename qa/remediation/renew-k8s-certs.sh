#!/usr/bin/env bash
# Renew all kubeadm-managed Kubernetes certificates.
#
# Must be run as root (or via sudo) on dc01-vm-00 (192.168.122.100).
#
# After running:
#   1. Control-plane static pods restart automatically when their manifests
#      are touched (kube-apiserver, etcd, etc.).
#   2. You must restart kubelet on EVERY node (control-plane + workers).
#   3. Your ~/.kube/config is updated so kubectl works again immediately.

set -euo pipefail

BACKUP_DIR="/etc/kubernetes/pki.bak.$(date +%Y%m%d_%H%M%S)"
KUBECONFIG_BAK="/etc/kubernetes/admin.conf.bak.$(date +%Y%m%d_%H%M%S)"

echo "=== [1/5] Backing up existing PKI and admin.conf ==="
cp -r /etc/kubernetes/pki "$BACKUP_DIR"
cp /etc/kubernetes/admin.conf "$KUBECONFIG_BAK"
echo "Backed up to: $BACKUP_DIR"

echo ""
echo "=== [2/5] Renewing all kubeadm-managed certificates ==="
kubeadm certs renew all

echo ""
echo "=== [3/5] Touching control-plane manifests to trigger pod restart ==="
# The kubelet watches /etc/kubernetes/manifests and restarts static pods
# when their manifest file mtime changes.
for manifest in /etc/kubernetes/manifests/*.yaml; do
    echo "  touch $manifest"
    touch "$manifest"
done

echo "Waiting 25s for control-plane pods to cycle..."
sleep 25

echo ""
echo "=== [4/5] Restarting kubelet on this node ==="
systemctl restart kubelet

echo ""
echo "=== [5/5] Updating ~/.kube/config with renewed certificate ==="
cp /etc/kubernetes/admin.conf ~/.kube/config
chown "$(id -u):$(id -g)" ~/.kube/config

echo ""
echo "=== Verifying renewed certificate expiry ==="
kubeadm certs check-expiration

echo ""
echo "=================================================="
echo "DONE — control-plane certificates renewed."
echo ""
echo "You must still restart kubelet on the WORKER NODES:"
echo "  ssh cisco@192.168.122.101 'sudo systemctl restart kubelet'"
echo "  ssh cisco@192.168.122.102 'sudo systemctl restart kubelet'"
echo "=================================================="
