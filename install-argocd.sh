#!/usr/bin/env bash
# Optional: installs ArgoCD and registers this repo's k8s/ folder as an Application.
# Run after setup.sh. ArgoCD is heavy, so skip it on low-memory machines unless you need GitOps.
set -euo pipefail
cd "$(dirname "$0")"

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=Established crd/applications.argoproj.io --timeout=120s
kubectl rollout status deployment/argocd-server -n argocd --timeout=300s
kubectl apply -f argocd/application.yaml

echo
echo "ArgoCD is ready. Admin password:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
echo
echo "Open it with: kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "Then visit https://localhost:8080 (username: admin) and click Sync on devops-vap-app."
