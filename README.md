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

The full step-by-step guide for starting this project, whether resuming on the same laptop or setting it up on a machine that has never seen it before, now lives in [START.md](START.md) rather than here, so there is one accurate copy instead of two that can drift apart.

Short version: on the same laptop, open separate terminals for `kubectl port-forward` to Grafana, Prometheus, and optionally ArgoCD, then run `python monitor.py` inside `ai-monitor/`. On a fresh machine, run `./install-tools.sh` then `./setup.sh`, optionally `./install-argocd.sh`, then set up `ai-monitor/` and, for Phase 2, `agent/`. See START.md for the exact commands and the order they need to run in.

## Challenges Faced and Lessons Learned

Building this on a resource-constrained laptop with 8GB of RAM surfaced real, practical DevOps problems, and debugging them turned out to be as instructive as building the happy path.

Running the full kube-prometheus-stack Helm chart, which includes Prometheus, Grafana, Alertmanager, and the Prometheus Operator, alongside ArgoCD's seven pods and the application pods pushed the node past 78 percent memory usage. Eventually the Kubernetes control plane itself, specifically kube-scheduler and kube-controller-manager, started crashing with TLS handshake timeout errors. The fix was swapping the heavy Helm-based monitoring stack for a lightweight, hand-written Prometheus and Grafana deployment with no operator and no Alertmanager, which roughly halved the total pod count, and later capping WSL2's own memory via .wslconfig so Windows always keeps enough headroom to stay responsive.

That lightweight setup was missing kube-state-metrics, which turned out to be the only component that exposes Kubernetes-level facts like pod restart counts. Plain Prometheus only sees raw container CPU and memory, not the fact that a pod restarted. This was diagnosed by querying Prometheus directly and getting empty results back, and fixed by installing just that one component through its official standalone manifests, then manually adding a scrape job to Prometheus's config since this setup has no auto-discovery. The same component went missing again after a later full cluster rebuild, which is exactly why it is now captured as a real YAML file under monitoring/ and installed automatically by setup.sh instead of being a one-off manual fix that only lives in shell history.

A more subtle bug: kubectl delete pod doesn't restart a container, it replaces the whole pod with a new name. The first version of the AI anomaly detector only checked whether the restart count had gone up for an existing pod name, which missed this case entirely. The fix was to also detect when a pod name that didn't exist in the previous check suddenly appears.

After several Docker and WSL restarts, old kubectl port-forward processes kept holding onto ports even though their terminal windows were long gone, causing "address already in use" errors. This was diagnosed with lsof -i :<port> and resolved by killing the specific orphaned process. The same restarts occasionally crashed the Kubernetes control plane itself with TLS handshake timeouts under load; the fastest reliable fix turned out to be docker restart devops-vap-control-plane rather than troubleshooting the control plane pods individually.

Google's Gemini API turned out to be mid-rollout of a new auth key format with an AQ. prefix that, at least at the time of this project, returns a 401 ACCESS_TOKEN_TYPE_UNSUPPORTED error for many accounts no matter how the request is authenticated. This is a known, currently open issue on Google's side rather than a bug in this code. The fix was switching to Groq, which has a stable, simple API key flow and a genuinely free tier — though even there, the actual current model name had to be looked up directly from Groq's own /v1/models endpoint rather than assumed, since model availability changes over time.

Secret hygiene turned out to need active discipline, not just a .gitignore. Across this project a GitHub token and a Discord webhook URL were each exposed more than once, mid-debugging, by pasting full file contents into chat instead of checking only a length or first few characters. Each time, the exposed credential was revoked and regenerated immediately rather than left in place. The lesson that stuck: verify secrets with commands like grep -o '^SOME_KEY=.\{0,8\}' .env or wc -c, and edit .env files directly rather than through shell one-liners (export $(grep ...), templated sed commands) that are easy to get subtly wrong without noticing.

Editing Kubernetes config with kubectl edit, which opens vi or nano, turned out to be risky under time pressure without being fluent in the editor. Switching to writing config as a full YAML file and applying it with kubectl apply -f was more reliable, since it's scriptable and reviewable rather than requiring careful live interactive editing.

Reproducibility needed to be built, not assumed. An early attempt to give this project a portable GitHub Codespaces setup via a .devcontainer config failed twice: first because the Python base image's bundled apt source for Yarn had an unreachable signing key, and again, after switching to a plain Ubuntu base image, because the Docker-in-Docker feature itself failed to install in that environment. Rather than keep fighting devcontainer internals, the simpler and more reliable fix was a plain install-tools.sh script that checks for and installs kind, kubectl, and helm on whatever machine it's run on, relying only on Docker already being present — which Codespaces' default image provides without any extra configuration.

Agent-generated output needs to be verified by actually using it, not just checked for a success status. Phase 2's Dockerfile generator initially looked correct because docker build exited 0, but the generated app had no server start call at all, so the container built fine and then exited in under a second — caught only by actually running the image and checking it stayed up, not by trusting the build result alone. The same lesson repeated at the Kubernetes layer: the agent's own final summary printed a kubectl port-forward command using the wrong port, because it assumed the generated Service's port always matched the container's port instead of reading the Service's real port back from the cluster. Both bugs were found by running the exact commands the tooling told me to run, rather than stopping at "it reported success."

## Roadmap and Next Steps

The AI-powered anomaly detection layer described in the original project plan is done — see ai-monitor/monitor.py.

The Autonomous DevOps Agent described in the original project plan is also done — see the Phase 2 section below and agent/. It onboards a repository it hasn't seen before, analyzes its stack, generates a tailored Dockerfile and Kubernetes manifests with its own build-and-retry loop, then deploys it, turning the project from infrastructure for one app into a tool that deploys apps.

What's left: Terraform generation and a generated CI/CD workflow file for the onboarded app. ai-monitor's live anomaly-detection pattern has been extended to watch apps the agent deploys, not just this project's own two services — see the Phase 2 section below for how.

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

### Connected to Phase 1's AI monitor

Every Deployment the agent generates is tagged with a `monitored: "true"` label. The Phase 1 AI monitor (`ai-monitor/monitor.py`) watches for that label in addition to its two original services, so any app the agent deploys is automatically picked up for restart and CPU anomaly detection, with no app name ever hardcoded anywhere.

This required one fix to the cluster setup: `kube-state-metrics` does not expose pod labels by default, only an explicit allowlist of them. `setup.sh` now passes `--metric-labels-allowlist=pods=[monitored]` to it so this works out of the box on a fresh machine, not just as a one-off manual patch.

### Scope and limitations

This supports single-service Python (Flask, FastAPI, Django) and Node repos with the application at the repository root. A monorepo with multiple services in subfolders, such as this project's own repo, is correctly detected as unsupported rather than silently guessed at incorrectly.

Not built: Terraform generation, and a generated CI/CD workflow file for an onboarded app. The "detect a failure and apply a fix" loop now exists for agent-deployed apps through the AI monitor connection above, but it currently explains and alerts rather than automatically applying a fix — a human still acts on the Discord message.

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
