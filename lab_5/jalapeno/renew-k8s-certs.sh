#!/usr/bin/env bash
#
# renew-k8s-certs.sh
#
# Renews kubeadm-managed Kubernetes control-plane certificates, restarts the
# static-pod containers so they pick up the new certs, and refreshes the
# admin kubeconfig for both root and the invoking user.
#
# Symptom this fixes:
#   kube-apiserver CrashLoopBackOff with logs showing:
#     x509: certificate has expired or is not yet valid
#   and `kubectl` returning:
#     dial tcp <api>:6443: connect: connection refused
#
# Usage:  sudo ./renew-k8s-certs.sh
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (use sudo)." >&2
  exit 1
fi

# The user who invoked sudo, so we can also drop a kubeconfig in their $HOME.
INVOKING_USER="${SUDO_USER:-}"
INVOKING_HOME=""
if [[ -n "$INVOKING_USER" && "$INVOKING_USER" != "root" ]]; then
  INVOKING_HOME="$(getent passwd "$INVOKING_USER" | cut -d: -f6)"
fi

log() { printf '\n=== %s ===\n' "$*"; }

log "Current certificate expiration"
kubeadm certs check-expiration || true

log "Renewing all control-plane certificates"
kubeadm certs renew all

log "New certificate expiration"
kubeadm certs check-expiration || true

log "Restarting control-plane static-pod containers"
# Force kubelet to recreate the static pods with the new certs by removing
# the running containers. kubelet will restart them automatically.
CP_CONTAINERS=$(crictl ps -a --no-trunc 2>/dev/null \
  | awk '/kube-apiserver|kube-controller-manager|kube-scheduler|etcd/ {print $1}')

if [[ -n "$CP_CONTAINERS" ]]; then
  echo "$CP_CONTAINERS" | xargs -r crictl rm -f
else
  echo "No control-plane containers found via crictl (is containerd the runtime?)."
fi

log "Refreshing /root/.kube/config"
mkdir -p /root/.kube
cp -f /etc/kubernetes/admin.conf /root/.kube/config
chown root:root /root/.kube/config
chmod 600 /root/.kube/config

if [[ -n "$INVOKING_HOME" && -d "$INVOKING_HOME" ]]; then
  log "Refreshing ${INVOKING_HOME}/.kube/config for user '${INVOKING_USER}'"
  install -d -o "$INVOKING_USER" -g "$INVOKING_USER" "${INVOKING_HOME}/.kube"
  cp -f /etc/kubernetes/admin.conf "${INVOKING_HOME}/.kube/config"
  chown "$INVOKING_USER":"$INVOKING_USER" "${INVOKING_HOME}/.kube/config"
  chmod 600 "${INVOKING_HOME}/.kube/config"
fi

log "Waiting for kube-apiserver to come back up"
for i in {1..30}; do
  if kubectl --kubeconfig=/root/.kube/config get --raw='/healthz' >/dev/null 2>&1; then
    echo "API server is healthy."
    break
  fi
  printf '.'
  sleep 2
done
echo

log "Cluster status"
kubectl --kubeconfig=/root/.kube/config get nodes -o wide || true
kubectl --kubeconfig=/root/.kube/config get pods -A || true

log "Done. Certificates renewed."
