# DevOps VAP Project — Self-Healing, Auto-Scaling Kubernetes Platform with AI Monitoring

A production-style microservices platform demonstrating the full CI/CD → GitOps → Kubernetes → Observability → AI-powered monitoring lifecycle, built for the ViMEET DevOps VAP (InLustro), Phase 1.

## What This Demonstrates

- Microservices architecture: two independent FastAPI services communicating over HTTP
- Full CI/CD lifecycle: automated pytest tests, Docker image builds (tagged with both `latest` and the git commit SHA), and registry pushes on every commit
- GitOps deployment: ArgoCD continuously syncs the cluster to match what's declared in this repo
- Self-healing infrastructure: Kubernetes automatically detects and recovers failed pods
- Auto-scaling: a Horizontal Pod Autoscaler reacts to real-time CPU load
- Observability: live Prometheus and Grafana dashboards for every service
- AI-powered anomaly detection: a Python service polls live Prometheus metrics, detects anomalies such as pod restarts or elevated CPU, asks an LLM to explain them in plain English, and posts alerts to Discord

## Architecture
Developer pushes code to GitHub
│
▼
GitHub Actions (CI/CD)
├─ Install dependencies
├─ Run pytest unit tests
├─ Build Docker image (users-service, orders-service)
└─ Push image to Docker Hub, tagged :latest and :<git-sha>
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
├─ Prometheus — scrapes live CPU/memory (cAdvisor) + pod metadata (kube-state-metrics)
└─ Grafana — dashboards for real-time visualization
│
▼
AI Monitoring Layer (ai-monitor/monitor.py)
├─ Polls Prometheus every 15s for restart counts + CPU usage
├─ Detects anomalies (new/replaced pods, elevated CPU)
├─ Sends anomaly details to Groq (Llama 3 / GPT-OSS) for a plain-English explanation
└─ Posts the alert + explanation to a Discord webhook

## Services

| Service | Port | Responsibility |
|---|---|---|
| users-service | 8001 | CRUD API for users (in-memory store) |
| orders-service | 8002 | Creates orders; validates the user exists by calling users-service over HTTP |
| ai-monitor | background script | Polls Prometheus, detects anomalies, calls Groq, posts to Discord |

Both API services expose a /health endpoint used by Kubernetes liveness and readiness probes.

## Tech Stack

| Layer | Tools |
|---|---|
| Language / Framework | Python, FastAPI, uvicorn |
| Testing | pytest, FastAPI TestClient, unittest.mock |
| Containers | Docker |
| CI/CD | GitHub Actions |
| Registry | Docker Hub |
| Orchestration | Kubernetes (kind — local cluster) |
| GitOps | ArgoCD |
| Monitoring | Prometheus, Grafana, kube-state-metrics |
| Autoscaling | Kubernetes HPA (metrics-server) |
| AI / LLM | Groq API (Llama 3 / GPT-OSS models) |
| Notifications | Discord webhook |

## Repository Structure
devops-vap/
├── users-service/
│ ├── main.py
│ ├── test_main.py
│ ├── requirements.txt
│ └── Dockerfile
├── orders-service/
│ ├── main.py
│ ├── test_main.py
│ ├── requirements.txt
│ └── Dockerfile
├── ai-monitor/
│ ├── monitor.py
│ ├── requirements.txt
│ └── .env.example
├── k8s/
│ ├── users-deployment.yaml
│ ├── orders-deployment.yaml
│ └── hpa.yaml
├── .github/workflows/
│ └── ci-cd.yaml
└── README.md

## Proven Capabilities

These were all demonstrated live during development, not just written and assumed to work.

Self-healing: manually deleting a pod triggers automatic replacement within seconds, maintaining the declared replica count.

Auto-scaling: generating concurrent load against orders-service triggers the HPA to scale from 2 to 5 replicas based on live CPU metrics, then scale back down automatically once load subsides.

CI/CD: a git push to main automatically runs pytest, builds both Docker images, and pushes them to Docker Hub tagged with both latest and the commit SHA, with no manual steps.

GitOps: a change to any file under k8s/, such as a replica count, is automatically detected by ArgoCD as configuration drift and applied to the live cluster on sync, with no manual kubectl apply.

AI monitoring: deleting a pod is detected within 15 seconds, the anomaly is sent to an LLM, and a plain-English explanation with a concrete next step is posted to Discord, fully automated end to end.

---

## Cold-Start Guide

Use this after closing all terminals or restarting your laptop. This project runs entirely locally on a kind cluster inside Docker Desktop/WSL2. Docker containers restart automatically, but every kubectl port-forward and the ai-monitor script need to be started fresh each time.

### Terminal 1: verify the cluster is alive

```bash
docker ps
```

You should see devops-vap-control-plane with status Up. If Docker Desktop isn't running yet, open it from Windows and wait 30 to 60 seconds, then retry.

```bash
sleep 30
kubectl get pods -A
```

Confirm all pods across the default, argocd, monitoring, and kube-system namespaces show Running. If some show errors right after boot, wait another 30 to 60 seconds and check again — this is normal.

### Terminal 2: Grafana dashboard

```bash
kubectl port-forward -n monitoring svc/grafana 3000:3000
```

Leave this running. Open localhost:3000 in your browser (login admin / admin123, or check your notes if the password was changed).

### Terminal 3: Prometheus

```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

Leave this running. Needed by both Grafana and the AI monitor.

### Terminal 4: free for one-off commands

No standing command here. Use it for kubectl get pods, kubectl delete pod, and similar checks.

### Terminal 5: orders-service (only for load-testing auto-scaling)

```bash
kubectl port-forward svc/orders-service 8002:8002
```

### Terminal 6: ArgoCD (only when demonstrating GitOps)

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Open https://localhost:8080 and click through the self-signed certificate warning. Username is admin. Get the password with:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

### Terminal 7: AI monitoring layer

```bash
cd ~/devops-vap/ai-monitor
source venv/bin/activate
python monitor.py
```

Leave this running. It polls every 15 seconds and posts to Discord automatically when it detects a pod restart, a pod replacement, or elevated CPU.

### Quick smoke test

Once everything above is running, in Terminal 4:

```bash
kubectl get pods
kubectl delete pod <any-orders-service-pod-name>
```

Within about 15 to 30 seconds you should see the pod replaced, a new line appear on the Grafana dashboard, and an alert posted to Discord with an AI-generated explanation.

If any kubectl port-forward fails with "address already in use," an old process is still holding that port from a previous session. Find and kill it:

```bash
lsof -i :<port-number>
kill -9 <PID>
```

---

## Challenges Faced and Lessons Learned

Building this on a resource-constrained laptop with 8GB of RAM surfaced real, practical DevOps problems, and debugging them turned out to be as instructive as building the happy path.

Running the full kube-prometheus-stack Helm chart, which includes Prometheus, Grafana, Alertmanager, and the Prometheus Operator, alongside ArgoCD's seven pods and the application pods pushed the node past 78 percent memory usage. Eventually the Kubernetes control plane itself, specifically kube-scheduler and kube-controller-manager, started crashing with TLS handshake timeout errors. The fix was swapping the heavy Helm-based monitoring stack for a lightweight, hand-written Prometheus and Grafana deployment with no operator and no Alertmanager, which roughly halved the total pod count.

That lightweight setup was missing kube-state-metrics, which turned out to be the only component that exposes Kubernetes-level facts like pod restart counts. Plain Prometheus only sees raw container CPU and memory, not the fact that a pod restarted. This was diagnosed by querying Prometheus directly and getting empty results back, and fixed by installing just that one component through its official standalone manifests, then manually adding a scrape job to Prometheus's config since this setup has no auto-discovery.

A more subtle bug: kubectl delete pod doesn't restart a container, it replaces the whole pod with a new name. The first version of the AI anomaly detector only checked whether the restart count had gone up for an existing pod name, which missed this case entirely. The fix was to also detect when a pod name that didn't exist in the previous check suddenly appears.

After several Docker and WSL restarts, old kubectl port-forward processes kept holding onto ports even though their terminal windows were long gone, causing "address already in use" errors. This was diagnosed with lsof -i :<port> and resolved by killing the specific orphaned process.

Google's Gemini API turned out to be mid-rollout of a new auth key format with an AQ. prefix that, at least at the time of this project, returns a 401 ACCESS_TOKEN_TYPE_UNSUPPORTED error for many accounts no matter how the request is authenticated. This is a known, currently open issue on Google's side rather than a bug in this code. The fix was switching to Groq, which has a stable, simple API key flow and a genuinely free tier.

At one point during debugging, a GitHub token and a Discord webhook URL were briefly pasted somewhere they shouldn't have been. Both were revoked and regenerated immediately. Going forward, secrets get verified with commands that only reveal a length or a first few characters, never the full value, and .env files get edited directly rather than through shell one-liners that are easy to get subtly wrong.

Finally, editing Kubernetes config with kubectl edit, which opens vi or nano, turned out to be risky under time pressure without being fluent in the editor. Switching to writing config as a full YAML file and applying it with kubectl apply -f was more reliable, since it's scriptable and reviewable rather than requiring careful live interactive editing.

## Roadmap and Next Steps

The AI-powered anomaly detection layer described in the original project plan is done — see ai-monitor/monitor.py.

The next phase is the Autonomous DevOps Agent: extending this pipeline into a general-purpose agent that can onboard a repository it hasn't seen before, analyze its stack, generate a tailored Dockerfile, CI/CD workflow, and Kubernetes manifests, then deploy and monitor it. This turns the project from infrastructure for one app into a tool that deploys apps.

## Running Locally From a Fresh Clone

Requires Docker Desktop with the WSL2 backend, kind, kubectl, helm, and Python 3.11 or newer.

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

# 4. Set up ai-monitor
cd ai-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your real GROQ_API_KEY and DISCORD_WEBHOOK_URL
```

---
Built as part of the ViMEET DevOps VAP (InLustro) program, 2026.

## Phase 2: Autonomous DevOps Agent

The code in agent/ onboards a repository it has never seen before, with no human writing a Dockerfile or Kubernetes manifest by hand.

Given a GitHub repo URL, the agent:

1. Clones the repo and analyzes its structure to detect the language, framework, entry point, dependency file, and likely port, by reading files like requirements.txt and package.json rather than assuming.
2. Sends that analysis to an LLM (Groq, Llama 3 / GPT-OSS models) and asks it to generate a Dockerfile.
3. Actually builds that Dockerfile, then runs the resulting image and checks it stays up rather than exiting immediately — a build can succeed while the app itself never starts a server, and this step catches exactly that.
4. If the build or the runtime check fails, the error is fed back to the LLM, which gets up to three attempts to produce a working Dockerfile.
5. Generates a Kubernetes Deployment and Service from the same analysis, applies it to the cluster, and waits for the pod to reach Running — again with up to three attempts, each one informed by the previous failure's kubectl describe and logs output.
6. Prints a summary report: what stack it detected, how many attempts each stage took, and the exact commands to check the result yourself.

### Proven, not assumed

Run against render-examples/flask-hello-world, a minimal Flask app with no Dockerfile and a route handler that never calls app.run():

The agent's first Dockerfile attempt built successfully but the container exited immediately, since nothing in the source actually starts a server. The runtime check caught this, fed the failure back to the LLM, and the second attempt switched from python app.py to flask run --host=0.0.0.0 --port=5000, which starts the server through Flask's own CLI runner instead of relying on code that isn't there. That image builds, stays running, and serves real HTTP requests.

The Kubernetes manifest deployed successfully on the first attempt. Testing it directly:

kubectl port-forward svc/demo-app 8888:80
curl http://localhost:8888/
Hello, World!


An earlier version of the agent printed the wrong port-forward command in its final summary, assuming the Service port always matched the app's container port. The LLM had actually generated port: 80 for the Service (a reasonable default), which the agent's hardcoded hint didn't account for. This was caught by running the exact command the agent told me to run, not just checking that the pod said Running. The fix queries the real Service port from the cluster after deployment instead of assuming it.

### Scope and limitations

This supports single-service Python (Flask, FastAPI, Django) and Node repos with the application at the repository root. A monorepo with multiple services in subfolders, such as this project's own repo, is correctly detected as unsupported rather than silently guessed at incorrectly.

Not built in this phase: Terraform generation, a generated CI/CD workflow file, and an automated "detect a failure and apply a fix" loop for a deployed app. That last one is close to what ai-monitor already does in Phase 1 for this project's own services — extending that same approach to apply to an arbitrary onboarded app is the natural next step.

### Running it yourself

```bash
cd agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your real GROQ_API_KEY
python agent.py <github-repo-url> <app-name>
```
