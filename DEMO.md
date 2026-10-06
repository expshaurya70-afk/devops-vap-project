# Demo Walkthrough

This is the live sequence to run during a review. It assumes the environment is already up — see START.md if anything needs to be started first.

Open these terminals before you begin and keep them open throughout:

Terminal 1: free for kubectl commands.
Terminal 2: `kubectl port-forward -n monitoring svc/grafana 3000:3000` — leave running.
Terminal 3: `kubectl port-forward -n monitoring svc/prometheus 9090:9090` — leave running.
Terminal 4: free for load generation.

Have these browser tabs open: your GitHub repo's Actions tab, Grafana at localhost:3000 (dashboard "DevOps VAP - Services"), and your Discord channel.

## Part 1: CI/CD

Make a small, visible change and push it.

```bash
cd ~/devops-vap/orders-service
echo "# demo run $(date)" >> main.py
cd ~/devops-vap
git add .
git commit -m "Demo: trigger CI/CD pipeline"
git push
```

Switch to the GitHub Actions tab and show the pipeline running live: install dependencies, run pytest, build both Docker images, push to Docker Hub tagged with both `latest` and the commit SHA. Point out the pytest step actually running real tests, not a placeholder.

## Part 2: Self-healing

```bash
kubectl get pods
```

Pick an orders-service pod name, then:

```bash
kubectl delete pod <that-pod-name>
kubectl get pods
```

A replacement pod appears within seconds, keeping the replica count at 2. Narrate: liveness/readiness probes plus Kubernetes' own replica enforcement, no manual intervention.

## Part 3: Auto-scaling

Make sure the orders-service port-forward is running (start it in Terminal 1 if not: `kubectl port-forward svc/orders-service 8002:8002`, then switch to Terminal 4 for the load command).

Terminal 4:

```bash
for i in $(seq 1 10); do
  (for j in $(seq 1 500); do curl -s -o /dev/null http://localhost:8002/health; done) &
done
wait
```

Terminal 1, watch it scale:

```bash
kubectl get hpa -w
```

Point at the Grafana dashboard at the same time — CPU per pod should visibly spike, and the HPA replicas panel should climb from 2 toward 5. Ctrl+C the watch once it's climbed, and mention it scales back down automatically after load drops.

## Part 4: GitOps

If ArgoCD isn't running, start it first: `./install-argocd.sh` (takes a few minutes, adds memory load — only do this if the machine is handling things well).

Open `kubectl port-forward svc/argocd-server -n argocd 8080:443` in a spare terminal, visit `https://localhost:8080`, log in as admin.

Make a small change in the repo's k8s folder, push it, and show ArgoCD detect the drift on its own:

```bash
cd ~/devops-vap
sed -i 's/replicas: 2/replicas: 2  # demo touch/' k8s/orders-deployment.yaml
git add k8s/orders-deployment.yaml
git commit -m "Demo: touch orders-deployment for ArgoCD"
git push
```

Within ArgoCD's polling interval (a few minutes) the app flips to OutOfSync on its own. Click Sync, Synchronize. This is the "I changed a file on GitHub and my cluster updated itself" moment.

Revert the comment afterward so the file stays clean:

```bash
sed -i 's/replicas: 2  # demo touch/replicas: 2/' k8s/orders-deployment.yaml
git add k8s/orders-deployment.yaml
git commit -m "Revert demo touch"
git push
```

## Part 5: AI-powered monitoring

Start it if it isn't already running:

```bash
cd ~/devops-vap/ai-monitor
source venv/bin/activate
python monitor.py
```

Leave it running and visible. Go back to Terminal 1 and delete another pod:

```bash
kubectl get pods
kubectl delete pod <an-orders-service-pod-name>
```

Within about 15 seconds, the monitor terminal shows `[ANOMALY DETECTED]`, calls Groq, and posts to Discord. Switch to the Discord tab and show the actual message: the anomaly description plus the AI-written explanation and suggested next step.

## Part 6: Phase 2 — the autonomous agent

```bash
cd ~/devops-vap/agent
source venv/bin/activate
python agent.py https://github.com/render-examples/flask-hello-world demo-app
```

This takes 1 to 3 minutes. Narrate while it runs: it clones a repo it has never seen, detects the stack, asks an LLM for a Dockerfile, actually builds and runtime-tests it, retries with the real error if something's wrong, then does the same for Kubernetes manifests.

If you want to show the retry loop specifically, this exact repo is known to need one attempt-2 fix (the source has no `app.run()` call), which the agent catches and corrects on its own — worth pointing out explicitly since it's genuine reasoning, not a lucky first guess.

When it finishes, use the exact commands it prints at the end:

```bash
kubectl get pods -l app=demo-app
kubectl port-forward svc/demo-app 8888:<port-it-printed>
curl http://localhost:8888/
```

Clean up afterward:

```bash
kubectl delete deployment,service demo-app
docker rmi demo-app:v1
```

## If something breaks mid-demo

A port-forward fails with "address already in use": an old process is holding it.

```bash
lsof -i :<port-number>
kill -9 <PID>
```

A kubectl command times out or refuses to connect: Docker Desktop likely isn't running, or the kind container needs a moment after a restart.

```bash
docker ps
sleep 30
kubectl get pods -A
```

Things generally feel sluggish or pods start failing probes under load: this is resource pressure on an 8GB machine, not a bug. The fastest recovery is restarting just the cluster container, which clears stuck processes without losing anything:

```bash
docker restart devops-vap-control-plane
```

Give it 60-90 seconds after that before running anything else.

## What to say if asked what's not built yet

Terraform generation and a generated CI/CD workflow for Phase 2's onboarded apps aren't built. Extending the Phase 1 AI-monitor pattern to watch apps the agent deploys, not just this project's own two services, is the planned next step — see the Roadmap section in README.md.

## Part 7: The AI monitor watching an agent-deployed app

This connects Part 5 and Part 6: the AI monitor isn't limited to the two original services, it automatically watches anything the agent deploys.

Make sure `ai-monitor/monitor.py` is running (same as Part 5). Then run the agent against a small repo, same as Part 6:

```bash
cd ~/devops-vap/agent
source venv/bin/activate
python agent.py https://github.com/render-examples/flask-hello-world watch-demo
```

While it's deploying, point out that the generated Deployment includes a `monitored: "true"` label — that's what makes it visible to the AI monitor without any hardcoded app name.

Once it's deployed, confirm it over in the monitor's terminal — within 15 seconds its baseline restart counts should include a `watch-demo-...` pod alongside `users-service` and `orders-service`, picked up purely through the label.

Trigger an anomaly on it specifically:

```bash
kubectl get pods -l app=watch-demo
kubectl delete pod <the-watch-demo-pod-name>
```

Within the next cycle, the monitor detects the replacement pod, calls Groq, and posts to Discord — and the explanation will reference `watch-demo` by name, proving it's reasoning about this specific app, not a hardcoded message.

Clean up afterward:

```bash
kubectl delete deployment,service watch-demo
docker rmi watch-demo:v1
```

### A real bug found while building this

`kube-state-metrics` does not expose pod labels by default — only the labels you explicitly allow. The fix was adding `--metric-labels-allowlist=pods=[monitored]` to its deployment args, both live on the cluster and in `setup.sh`, so a fresh machine gets this working out of the box rather than silently missing it. This was only caught by querying Prometheus directly and noticing `kube_pod_labels` came back completely empty — worth mentioning if asked how the label-based watching was verified, not just assumed to work.
