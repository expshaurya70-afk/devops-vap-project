#!/usr/bin/env bash
# Installs kind, kubectl and helm on a fresh Linux machine that already has Docker.
# Codespaces' default image already includes Docker, so this is all it needs.
set -euo pipefail

if ! command -v kind >/dev/null; then
  curl -sSLo /tmp/kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64
  sudo install /tmp/kind /usr/local/bin/kind
fi

if ! command -v kubectl >/dev/null; then
  curl -sSLo /tmp/kubectl "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  sudo install /tmp/kubectl /usr/local/bin/kubectl
fi

if ! command -v helm >/dev/null; then
  curl -sS https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | sudo bash
fi

kind --version
kubectl version --client
helm version --short
docker --version
