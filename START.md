# How to Start and Run This Project

Two situations are covered here: resuming on the same laptop after closing terminals or rebooting, and setting the whole project up on a machine that has never seen it before.

## Situation 1: Resuming on the same laptop

Docker containers restart on their own, but every kubectl port-forward and both Python scripts (ai-monitor and agent) stop when their terminal closes and need to be started again.

Terminal 1: check the cluster is alive.

```bash
docker ps
```

You should see devops-vap-control-plane with status Up. If Docker Desktop isn't running, open it from Windows and wait 30 to 60 seconds before retrying.

```bash
sleep 30
kubectl get pods -A
```

Confirm pods in default, argocd (if installed), monitoring, and kube-system all show Running.

Terminal 2: Grafana.

```bash
kubectl port-forward -n monitoring svc/grafana 3000:3000
```

Open localhost:3000, log in with admin and admin123, open the dashboard "DevOps VAP - Services" under Dashboards.

Terminal 3: Prometheus, needed by both Grafana and the AI monitor.

```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

Terminal 4: free for one-off commands such as kubectl get pods or kubectl delete pod.

Terminal 5: orders-service, only needed when demonstrating auto-scaling.

```bash
kubectl port-forward svc/orders-service 8002:8002
```

Terminal 6: ArgoCD, only needed when demonstrating GitOps. Skip this if ArgoCD isn't installed on this cluster.

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Open https://localhost:8080, click through the certificate warning, log in with admin and:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

Terminal 7: the AI monitoring layer.

```bash
cd ~/devops-vap/ai-monitor
source venv/bin/activate
python monitor.py
```

Leave running. It polls every 15 seconds and posts to Discord when it detects a pod restart, a pod replacement, or elevated CPU. This also automatically watches any app deployed by the Phase 2 agent (see agent/), through a monitored="true" label on the Deployment it generates — no app name is ever hardcoded.

Terminal 8: the Phase 2 agent, only when demonstrating it.

```bash
cd ~/devops-vap/agent
source venv/bin/activate
python agent.py <github-repo-url> <app-name>
```

## Quick smoke test

Once Terminals 1 to 3 and 7 are running, in Terminal 4:

```bash
kubectl get pods
kubectl delete pod <any-orders-service-pod-name>
```

Within 15 to 30 seconds: the pod gets replaced, a new line appears on the Grafana dashboard, and an alert with an AI-written explanation shows up in Discord.

If a port-forward fails with "address already in use," an old process from a previous session is still holding that port.

```bash
lsof -i :<port-number>
kill -9 <PID>
```

## Situation 2: Setting this up on a machine that has nothing on it yet

Needed first: Docker, and a clone of this repo.

```bash
git clone https://github.com/expshaurya70-afk/devops-vap-project.git
cd devops-vap-project
```

Step 1: install kind, kubectl and helm if they aren't already present.

```bash
./install-tools.sh
```

Step 2: bring up the cluster, the app, and monitoring in one go.

```bash
./setup.sh
```

This creates the kind cluster, builds and loads the users-service and orders-service images, applies the k8s manifests, installs metrics-server, installs kube-state-metrics with the label allowlist the AI monitor needs, and installs Prometheus and Grafana with the dashboard already provisioned. Takes a few minutes. Ends by printing the full pod list — everything should show Running.

Step 3 (optional): ArgoCD, only if demonstrating GitOps. Adds seven pods, so skip on a machine with 8GB or less unless specifically needed.

```bash
./install-argocd.sh
```

Prints the admin password at the end. Open with:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Visit https://localhost:8080, log in as admin, open devops-vap-app, click Sync.

Step 4: the AI monitoring layer.

```bash
cd ai-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit .env and fill in a real GROQ_API_KEY (free at console.groq.com) and a real DISCORD_WEBHOOK_URL. Then:

```bash
python monitor.py
```

Step 5 (optional): the Phase 2 agent.

```bash
cd ../agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in the same GROQ_API_KEY. Then:

```bash
python agent.py <github-repo-url> <app-name>
```

Step 6: open the dashboards. In separate terminals:

```bash
kubectl port-forward -n monitoring svc/grafana 3000:3000
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

Grafana is at localhost:3000, login admin and admin123. The dashboard "DevOps VAP - Services" is already provisioned.

## If something goes wrong

A pod fails its liveness or readiness probe with a connection error: check the Dockerfile's EXPOSE and CMD port actually matches what the deployment YAML and probes expect.

A kubectl command times out or refuses to connect: Docker Desktop or the kind container probably isn't running yet.

```bash
docker ps
sleep 30
kubectl get pods -A
```

The whole cluster seems to be crashing under load, with things like "TLS handshake timeout": this is resource exhaustion on an 8GB laptop, not a bug. Fastest recovery:

```bash
docker restart devops-vap-control-plane
```

Give it 60 to 90 seconds afterward.

A Prometheus query for restart counts or pod labels comes back empty: either kube-state-metrics isn't installed, or, for labels specifically, it's running without the --metric-labels-allowlist flag. setup.sh handles both, but on an older cluster check with:

```bash
kubectl get deployment kube-state-metrics -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}'
```

An LLM call to Gemini fails with ACCESS_TOKEN_TYPE_UNSUPPORTED: a known issue with a newer Google API key format, not a bug in this code. This project uses Groq instead.

The agent's Dockerfile build succeeds but the container exits immediately: the source app likely has no server start call. The agent's own runtime check catches this and retries with the error fed back to the LLM — this is expected behavior, not a failure, as long as a later attempt succeeds.

Never paste a real API key, token, or webhook URL anywhere outside your own .env file. To check a secret without exposing it: `grep -o '^SOME_KEY=.\{0,8\}' .env` for a prefix, or `wc -c` for a length.
