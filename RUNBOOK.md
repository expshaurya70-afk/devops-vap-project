# Runbook: Run Everything From the Beginning

This is the one-stop guide for starting the whole project and walking through every part of it. It assumes a Windows laptop with WSL2 (Ubuntu) and Docker Desktop, and the project at ~/devops-vap. Each step says which terminal to use and what you should see.

Open each terminal as a new Ubuntu (WSL) tab and rename the tab with its number so you never mix them up.

Terminal 1: general kubectl and git commands.
Terminal 2: Grafana port-forward. Leave running.
Terminal 3: Prometheus port-forward. Leave running.
Terminal 4: load generation and spare commands.
Terminal 5: orders-service port-forward, only for the autoscaling demo.
Terminal 6: ArgoCD port-forward, only for the GitOps demo.
Terminal 7: the AI monitor. Leave running.
Terminal 8: the Phase 2 agent.

## Step 0: Turn on Docker

Open Docker Desktop from the Windows Start menu. Wait until the bottom-left of its window says the engine is running. This usually takes 30 to 60 seconds after a fresh boot. Everything else depends on this, because the Kubernetes cluster is a Docker container.

## Step 1: Check the cluster (Terminal 1)

```bash
docker ps
```

You should see one container named devops-vap-control-plane with status Up. If you see "command not found in this WSL distro", open Docker Desktop, go to Settings, Resources, WSL Integration, and switch on your Ubuntu distro.

```bash
sleep 30
kubectl get nodes
kubectl get pods -A
```

You should see the node Ready, then pods all Running: two users-service, two orders-service, grafana and prometheus in the monitoring namespace, kube-state-metrics and metrics-server in kube-system, and the argocd pods if ArgoCD is installed. Right after boot some pods may show errors for a minute. Wait and run the command again before assuming anything is wrong.

If docker ps shows no devops-vap container at all, the cluster doesn't exist on this machine. Build it from scratch (takes about five minutes, ends by printing the pod list):

```bash
cd ~/devops-vap
./install-tools.sh
./setup.sh
```

Never run kind delete cluster unless you mean to wipe everything. It removes ArgoCD and all cluster state, and you would have to rebuild with setup.sh and install-argocd.sh.

## Step 2: Grafana (Terminal 2)

```bash
kubectl port-forward -n monitoring svc/grafana 3000:3000
```

You should see "Forwarding from 127.0.0.1:3000". Open localhost:3000, log in with admin and admin123, then open Dashboards and the dashboard named "DevOps VAP - Services". It has five panels: CPU per pod, memory per pod, HPA replicas, running pods, and container restarts. Running pods normally reads 4. If the password is rejected, use a private window so autofill can't interfere. If that fails:

```bash
kubectl exec -n monitoring deploy/grafana -- grafana cli admin reset-admin-password admin123
```

## Step 3: Prometheus (Terminal 3)

```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

You should see "Forwarding from 127.0.0.1:9090". Both Grafana and the AI monitor need this to be running.

## Step 4: Start the AI monitor (Terminal 7)

```bash
cd ~/devops-vap/ai-monitor
source venv/bin/activate
python monitor.py
```

You should see "AI monitoring layer started", then a "Baseline restart counts" line listing your four pods, then every 15 seconds "Checking for anomalies..." followed by "No anomalies this cycle." If you get "connection refused" on port 9090, Terminal 3 isn't running.

Quick check that Discord is wired up (Terminal 1):

```bash
cd ~/devops-vap/ai-monitor
source venv/bin/activate
python3 -c "
from dotenv import load_dotenv
import os, requests
load_dotenv()
r = requests.post(os.getenv('DISCORD_WEBHOOK_URL'), json={'content': 'webhook check'})
print(r.status_code)
"
```

204 means Discord accepted it. The message lands in the channel where the webhook was created, which is on the Discord account that owns that server. If you can't see it, you are probably logged into a different Discord account.

## Demo A: Self-healing and the AI alert (Terminal 1)

```bash
kubectl get pods
kubectl delete pod <an-orders-service-pod-name>
kubectl get pods
```

You should see a replacement pod appear within seconds, back to two orders-service pods. Within about 15 seconds Terminal 7 prints "[ANOMALY DETECTED] New pod ... appeared" and then "Posted to Discord." In Discord you should see a message with the alert, an AI-written explanation, and a suggested next step. In Grafana, the pod lines and the restarts panel change.

## Demo B: Auto-scaling

Terminal 5:

```bash
kubectl port-forward svc/orders-service 8002:8002
```

Terminal 4:

```bash
for i in $(seq 1 10); do
  (for j in $(seq 1 500); do curl -s -o /dev/null http://localhost:8002/health; done) &
done
wait
```

Terminal 1:

```bash
kubectl get hpa -w
```

You should see the cpu figure climb past 50 percent and REPLICAS rise from 2 toward 5 over a minute or two. In Grafana, CPU spikes and the HPA replicas panel climbs. Press Ctrl+C on the watch when it has scaled. It scales back down by itself after about five minutes of low load. Keep it at 10 parallel loops. Twenty overloaded metrics-server on this 8GB machine. Stop Terminal 5 afterward to save memory.

## Demo C: CI/CD (Terminal 1)

```bash
cd ~/devops-vap/orders-service
echo "# demo run $(date)" >> main.py
cd ~/devops-vap
git add .
git commit -m "Demo: trigger CI/CD pipeline"
git push
```

At the Password prompt, paste your GitHub personal access token, not your account password. Open the Actions tab of the repo. You should see a workflow run with two jobs, one for users-service and one for orders-service. The steps are checkout, set up Python, install dependencies, run tests (4 tests pass for users-service, 3 for orders-service), log in to Docker Hub, then build and push. Both jobs go green. On Docker Hub, each image shows two tags: latest and the commit SHA. Note that the cluster runs locally built v1 images, so this pipeline publishes images but does not redeploy them. See Remaining below.

## Demo D: GitOps with ArgoCD

First check ArgoCD is installed:

```bash
kubectl get pods -n argocd
```

If it says no resources found, run ./install-argocd.sh from ~/devops-vap. It takes a few minutes, adds memory load, and prints the admin password at the end.

Terminal 6:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Open https://localhost:8080, click Advanced then Proceed past the certificate warning, and log in as admin. The password is printed by install-argocd.sh, or fetch it with:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

You should see devops-vap-app showing Synced and Healthy. If the app is missing, run kubectl apply -f argocd/application.yaml and refresh. Now change users-service from 2 to 3 replicas in Git (Terminal 1):

```bash
cd ~/devops-vap
sed -i 's/replicas: 2/replicas: 3/' k8s/users-deployment.yaml
grep -n "replicas" k8s/users-deployment.yaml
git add k8s/users-deployment.yaml
git commit -m "Demo: scale users-service to 3 replicas"
git push
```

In the ArgoCD UI, click Refresh on the app card. It should turn OutOfSync. Click Sync, then Synchronize, then check:

```bash
kubectl get pods -l app=users-service
```

You should see three pods. This uses users-service on purpose, because orders-service replicas are managed by the autoscaler and ArgoCD deliberately ignores that field. Revert afterward:

```bash
sed -i 's/replicas: 3/replicas: 2/' k8s/users-deployment.yaml
git add k8s/users-deployment.yaml
git commit -m "Revert demo: users-service back to 2 replicas"
git push
```

Refresh and Sync again in ArgoCD, and the third pod goes away.

## Demo E: The Phase 2 agent (Terminal 8)

```bash
cd ~/devops-vap/agent
source venv/bin/activate
python agent.py https://github.com/render-examples/flask-hello-world demo-app
```

This takes about two to three minutes. You should see the detected stack (python, flask, app.py, port 5000), then the Dockerfile stage. Attempt 1 builds but fails the runtime check, because the container exits right away. The source has no app.run() call. Attempt 2 switches to flask run and succeeds. Then the manifest stage deploys, and the report ends with RESULT: SUCCESS and a port-forward command. Run exactly the command it prints (the service port can differ between runs), then in another terminal:

```bash
curl http://localhost:8888/
```

You should see Hello, World!

## Demo F: The monitor watching the agent's app

The agent labels every Deployment it creates with monitored: "true", and the AI monitor watches that label, so no app name is hardcoded anywhere. While the monitor is running (Terminal 7), the new demo-app pod will probably be flagged as a new pod on its own, since any pod name it hasn't seen counts as an anomaly. To trigger an alert deliberately (Terminal 1):

```bash
kubectl get pods -l app=demo-app
kubectl delete pod <the-demo-app-pod-name>
```

Within about 15 seconds, Discord should show an alert that mentions demo-app by name. Clean up afterward:

```bash
kubectl delete deployment,service demo-app
docker rmi demo-app:v1
```

## Shutting down

Press Ctrl+C in Terminals 7, 6, 5, 3 and 2. The cluster keeps its state while Docker Desktop is running. To free memory, quit Docker Desktop, and the cluster container comes back the next time you open it.

## If something goes wrong

A port-forward says address already in use: an old process holds the port. Run lsof -i :PORT, then kill -9 PID.

kubectl times out or refuses to connect: Docker Desktop or the cluster container is still starting. Run docker ps, wait a minute, retry. If the whole cluster is sluggish or throwing TLS handshake timeouts, run docker restart devops-vap-control-plane and wait 60 to 90 seconds.

A Prometheus query for pod labels comes back empty: kube-state-metrics is running without its label allowlist. setup.sh sets it, but you can check with kubectl get deployment kube-state-metrics -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}'.

Never paste a real API key, token or webhook URL into a chat or a file in the repo. Check a secret without showing it with grep -o '^KEY=.\{0,8\}' .env.

## Project status

Done, Phase 1:
Two FastAPI microservices that call each other over HTTP, with health endpoints. Docker images for both. Kubernetes deployment with liveness and readiness probes, resource requests, and two replicas each. Self-healing, proven live. Horizontal Pod Autoscaler from 2 to 5 replicas, proven live. GitHub Actions pipeline with seven real pytest tests, Docker builds, and pushes to Docker Hub tagged latest and commit SHA. Prometheus and Grafana with kube-state-metrics, and a dashboard provisioned from the repo. ArgoCD GitOps with the Application defined in the repo. AI anomaly detection with Groq and Discord alerts.

Done, Phase 2:
Repo analyzer. Dockerfile generation with build and runtime verification and up to three retries that feed the real error back to the LLM. Kubernetes manifest generation with deploy verification and retries. One-command CLI with a readable report. Generated apps are labeled so the AI monitor watches them automatically.

Done, tooling and docs:
setup.sh, install-tools.sh and install-argocd.sh for rebuilding on a machine from scratch. README.md, START.md, DEMO.md and this RUNBOOK.md.

Remaining, from the original plan:
Trivy image scanning and SonarQube code scanning in the pipeline (a pytest stage stands in for both). Terraform and Ansible. Deployment to AWS or EKS, since everything runs on a local kind cluster. Centralized logging with Loki or ELK.

Remaining, gaps worth closing:
The CI/CD loop is not closed. The pipeline pushes images to Docker Hub, but the manifests point at locally built v1 images, so a code push does not change what runs in the cluster. Closing it means pointing the manifests at the Docker Hub image and having the pipeline commit the new commit-SHA tag into k8s/ so ArgoCD deploys it.
The agent has been tested against one repo. Testing two or three more, including a Node one, is still to do. Monorepos are detected as unsupported.
The agent does not generate Terraform or a CI/CD workflow for the apps it onboards, and the monitor alerts and explains but does not apply fixes automatically.
Rebuilding on another machine has only been verified on this laptop. The Codespaces attempt stalled while waiting for Prometheus and was never diagnosed.
Demo passwords (admin123) are in the repo, and the services store data in memory only.
