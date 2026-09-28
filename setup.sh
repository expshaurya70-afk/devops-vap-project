#!/usr/bin/env bash
# Bootstraps the whole project on a fresh machine that has docker, kind and kubectl.
set -euo pipefail

CLUSTER=devops-vap
cd "$(dirname "$0")"

echo "==> 1/6 Cluster"
if kind get clusters | grep -qx "$CLUSTER"; then
  echo "Cluster already exists, reusing it"
else
  kind create cluster --name "$CLUSTER"
fi
kubectl config use-context "kind-$CLUSTER"
kubectl wait --for=condition=Ready node --all --timeout=180s

echo "==> 2/6 Build and load app images"
for svc in users-service orders-service; do
  docker build -t "$svc:v1" "./$svc"
  kind load docker-image "$svc:v1" --name "$CLUSTER"
done

echo "==> 3/6 Deploy the app"
kubectl apply -f k8s/

echo "==> 4/6 metrics-server (needed by the HPA)"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
if ! kubectl get deployment metrics-server -n kube-system \
     -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -q insecure-tls; then
  kubectl patch deployment metrics-server -n kube-system --type=json \
    -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
fi

echo "==> 5/6 kube-state-metrics (pod restart counts for the AI monitor)"
BASE=https://raw.githubusercontent.com/kubernetes/kube-state-metrics/main/examples/standard
for f in cluster-role-binding cluster-role deployment service-account service; do
  kubectl apply -f "$BASE/$f.yaml"
done

echo "==> 6/6 Prometheus and Grafana"
kubectl apply -f monitoring/prometheus.yaml   # creates the monitoring namespace, so it goes first
kubectl apply -f monitoring/grafana-dashboard.yaml
kubectl apply -f monitoring/grafana.yaml
kubectl rollout status deployment/prometheus -n monitoring --timeout=180s
kubectl rollout status deployment/grafana -n monitoring --timeout=180s

echo
echo "Done. Current pods:"
kubectl get pods -A
echo
echo "Next, open separate terminals for:"
echo "  kubectl port-forward -n monitoring svc/grafana 3000:3000"
echo "  kubectl port-forward -n monitoring svc/prometheus 9090:9090"
echo "Then run ai-monitor (see README cold-start guide)."
