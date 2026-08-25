# DevOps VAP Project — Self-Healing, Auto-Scaling Kubernetes Platform

A production-style microservices platform demonstrating the full CI/CD → GitOps → Kubernetes → Observability lifecycle, built for the ViMEET DevOps VAP (InLustro), Phase 1.

## What This Demonstrates

- **Microservices architecture** — two independent FastAPI services communicating over HTTP
- **Full CI/CD lifecycle** — automated testing, Docker image builds, and registry pushes on every commit
- **GitOps deployment** — ArgoCD continuously syncs the cluster to match what's declared in this repo
- **Self-healing infrastructure** — Kubernetes automatically detects and recovers failed pods
- **Auto-scaling** — a Horizontal Pod Autoscaler reacts to real-time CPU load
- **Observability** — live Prometheus + Grafana dashboards for every service

## Architecture

```
Developer pushes code to GitHub
        │
        ▼
GitHub Actions (CI/CD)
   ├─ Install dependencies
   ├─ Run import/sanity checks
   ├─ Build Docker image (users-service, orders-service)
   └─ Push image to Docker Hub
        │
        ▼
ArgoCD (GitOps)
   └─ Detects repo changes, syncs cluster to match
        │
        ▼
Kubernetes Cluster (kind — local)
   ├─ users-service (Deployment, 2 replicas, Service)
   ├─ orders-service (Deployment, 2–5 replicas via HPA, Service)
   ├─ Liveness & readiness probes on /health
   └─ Horizontal Pod Autoscaler (CPU-based, 50% target)
        │
        ▼
Monitoring
   ├─ Prometheus — scrapes live CPU/memory per pod
   └─ Grafana — dashboards for real-time visualization
```

## Services

| Service | Port | Responsibility |
|---|---|---|
| `users-service` | 8001 | CRUD API for users (in-memory store) |
| `orders-service` | 8002 | Creates orders; validates the user exists by calling `users-service` over HTTP |

Both expose a `/health` endpoint used by Kubernetes liveness/readiness probes.

## Tech Stack

| Layer | Tools |
|---|---|
| Language / Framework | Python, FastAPI, uvicorn |
| Containers | Docker |
| CI/CD | GitHub Actions |
| Registry | Docker Hub |
| Orchestration | Kubernetes (kind — local cluster) |
| GitOps | ArgoCD |
| Monitoring | Prometheus, Grafana (via kube-prometheus-stack Helm chart) |
| Autoscaling | Kubernetes HPA (metrics-server) |

## Repository Structure

```
devops-vap/
├── users-service/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── orders-service/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── k8s/
│   ├── users-deployment.yaml
│   ├── orders-deployment.yaml
│   └── hpa.yaml
├── .github/workflows/
│   └── ci-cd.yaml
└── README.md
```

## Proven Capabilities (Demonstrated Live)

- **Self-healing**: manually deleting a pod triggers automatic replacement within seconds, maintaining the declared replica count.
- **Auto-scaling**: generating concurrent load against `orders-service` triggers the HPA to scale from 2 → 5 replicas based on live CPU metrics, then scale back down automatically once load subsides.
- **CI/CD**: a `git push` to `main` automatically runs checks, builds both Docker images, and pushes them to Docker Hub — no manual steps.
- **GitOps**: a change to any file under `k8s/` (e.g. replica count) is automatically detected by ArgoCD as configuration drift and applied to the live cluster on sync — no manual `kubectl apply`.

## Running Locally

Requires: Docker Desktop (WSL2 backend), `kind`, `kubectl`, `helm`, Python 3.11+.

```bash
# 1. Create the cluster
kind create cluster --name devops-vap

# 2. Build and load images
docker build -t users-service:v1 ./users-service
docker build -t orders-service:v1 ./orders-service
kind load docker-image users-service:v1 --name devops-vap
kind load docker-image orders-service:v1 --name devops-vap

# 3. Deploy
kubectl apply -f k8s/

# 4. Access services
kubectl port-forward svc/users-service 8001:8001
kubectl port-forward svc/orders-service 8002:8002
```

## Roadmap / Next Steps

- **AI-powered anomaly detection layer** — a Python service reading live Prometheus metrics, using an LLM to generate plain-English root-cause explanations for anomalies (e.g. pod restarts, latency spikes), and posting them to a team chat webhook.
- **Autonomous DevOps Agent (Phase 2)** — extending this pipeline into a general-purpose agent that can onboard an arbitrary repository: analyzing its stack, generating a tailored Dockerfile, CI/CD workflow, and Kubernetes manifests, then deploying and monitoring it — turning "infrastructure for one app" into "a tool that deploys apps."

---
Built as part of the ViMEET DevOps VAP (InLustro) program, 2026.
