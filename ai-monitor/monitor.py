import os
import time
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
PROMETHEUS_URL = "http://localhost:9090"  # via kubectl port-forward

groq_client = Groq(api_key=GROQ_API_KEY)

def query_prometheus(promql):
    """Run a PromQL query and return the result list."""
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": promql},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["data"]["result"]


def get_pod_restarts():
    """Returns {pod_name: restart_count} for pods in the default namespace."""
    results = query_prometheus('kube_pod_container_status_restarts_total{namespace="default"}')
    return {r["metric"]["pod"]: float(r["value"][1]) for r in results}


def get_pod_cpu():
    """Returns {pod_name: cpu_cores_used} for pods in the default namespace."""
    results = query_prometheus(
        'sum(rate(container_cpu_usage_seconds_total{namespace="default"}[2m])) by (pod)'
    )
    return {r["metric"]["pod"]: float(r["value"][1]) for r in results}


def ask_ai_for_explanation(anomaly_description):
    """Send the anomaly details to the LLM and get back a plain-English explanation."""
    prompt = (
        "You are a DevOps assistant monitoring a Kubernetes cluster running two "
        "FastAPI microservices (users-service and orders-service). "
        "Here is an anomaly detected in the live metrics:\n\n"
        f"{anomaly_description}\n\n"
        "In 2-3 short sentences, explain in plain English what likely happened "
        "and suggest one concrete next step. Be concise and practical."
    )

    response = groq_client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def post_to_discord(message):
    payload = {"content": message}
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    response.raise_for_status()


def check_for_anomalies(previous_restarts):
    """Compare current restart counts/pod names to previous check; return list of anomaly descriptions."""
    anomalies = []
    current_restarts = get_pod_restarts()
    cpu_usage = get_pod_cpu()

    # Case 1: a pod that existed before had its container restart count go up
    # (crash loop within the same pod)
    for pod, count in current_restarts.items():
        if pod in previous_restarts and count > previous_restarts[pod]:
            anomalies.append(
                f"Pod '{pod}' restarted (restart count went from "
                f"{int(previous_restarts[pod])} to {int(count)})."
            )

    # Case 2: a pod name that didn't exist last check just appeared
    # (this happens when a pod is deleted and Kubernetes creates a fresh replacement)
    if previous_restarts:  # skip this check on the very first run
        for pod in current_restarts:
            if pod not in previous_restarts:
                anomalies.append(
                    f"New pod '{pod}' appeared, likely replacing a deleted or "
                    f"failed pod (Kubernetes self-healing in action)."
                )

    for pod, cpu in cpu_usage.items():
        if cpu > 0.15:  # more than 150m CPU cores
            anomalies.append(f"Pod '{pod}' is using elevated CPU: {cpu:.3f} cores.")

    return anomalies, current_restarts


def main():
    print("AI monitoring layer started. Watching for anomalies every 15s...")
    previous_restarts = get_pod_restarts()
    print(f"Baseline restart counts: {previous_restarts}")

    while True:
        time.sleep(15)
        print("Checking for anomalies...")
        try:
            anomalies, previous_restarts = check_for_anomalies(previous_restarts)
            print(f"Current restart counts: {previous_restarts}")

            if not anomalies:
                print("No anomalies this cycle.")

            for anomaly in anomalies:
                print(f"[ANOMALY DETECTED] {anomaly}")
                explanation = ask_ai_for_explanation(anomaly)
                message = f"**DevOps Alert**\n{anomaly}\n\n**AI Explanation:**\n{explanation}"
                post_to_discord(message)
                print("Posted to Discord.")

        except Exception as e:
            print(f"Error during check: {e}")


if __name__ == "__main__":
    main()
