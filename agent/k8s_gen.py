import os
import subprocess
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-120b"
MAX_ATTEMPTS = 3
KIND_CLUSTER = "devops-vap"


def load_image_into_cluster(image_tag):
    result = subprocess.run(
        ["kind", "load", "docker-image", image_tag, "--name", KIND_CLUSTER],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to load image into kind: {result.stderr}")


def build_prompt(analysis, image_tag, app_name, previous_manifest=None, apply_error=None):
    port = analysis.get("port_guess") or 8000
    base = (
        "You are a DevOps assistant that writes Kubernetes manifests. "
        "Write a single YAML file containing a Deployment and a Service for this app.\n\n"
        f"App name to use for metadata.name: {app_name}\n"
        f"Container image (already built and loaded locally, do not add a registry prefix): {image_tag}\n"
        f"The app listens on container port: {port}\n\n"
        "Rules: respond with ONLY the YAML content, no explanation, no markdown code "
        "fences, no commentary. Use imagePullPolicy: Never since this image only exists "
        "locally in a kind cluster, not in any registry. Use 1 replica. Separate the "
        "Deployment and Service with '---'. Keep resource requests small "
        "(cpu: 50m, memory: 64Mi) since this is a demo on a small machine. "
        "Add the label monitored: \"true\" (alongside the app label) to the Deployment's "
        "pod template metadata.labels, so an external monitoring tool can find it."
    )
    if previous_manifest and apply_error:
        base += (
            "\n\nYour previous attempt failed to deploy. Here is what you wrote:\n"
            f"{previous_manifest}\n\n"
            f"Here is the error:\n{apply_error}\n\n"
            "Fix the YAML and respond with ONLY the corrected YAML content."
        )
    return base


def ask_for_manifest(analysis, image_tag, app_name, previous_manifest=None, apply_error=None):
    prompt = build_prompt(analysis, image_tag, app_name, previous_manifest, apply_error)
    response = groq_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return content


def try_deploy(manifest_content, app_name, manifest_path):
    with open(manifest_path, "w") as f:
        f.write(manifest_content)

    apply_result = subprocess.run(
        ["kubectl", "apply", "-f", manifest_path],
        capture_output=True, text=True,
    )
    if apply_result.returncode != 0:
        return False, f"kubectl apply failed:\n{apply_result.stderr}"

    # Wait up to 30s for a pod matching this app to be Running
    deadline = time.time() + 30
    last_status = "unknown"
    pod_name = None

    while time.time() < deadline:
        get_pods = subprocess.run(
            ["kubectl", "get", "pods", "-l", f"app={app_name}",
             "-o", "jsonpath={.items[0].metadata.name} {.items[0].status.phase}"],
            capture_output=True, text=True,
        )
        output = get_pods.stdout.strip()
        if output:
            parts = output.split(" ")
            pod_name = parts[0]
            last_status = parts[1] if len(parts) > 1 else "unknown"
            if last_status == "Running":
                return True, None
        time.sleep(2)

    # Didn't reach Running in time — gather diagnostics
    describe = ""
    logs = ""
    if pod_name:
        describe = subprocess.run(
            ["kubectl", "describe", "pod", pod_name],
            capture_output=True, text=True,
        ).stdout[-1500:]
        logs = subprocess.run(
            ["kubectl", "logs", pod_name],
            capture_output=True, text=True,
        ).stdout[-800:]

    error_summary = (
        f"Pod did not reach Running within 30s (last status: {last_status}).\n\n"
        f"kubectl describe pod (tail):\n{describe}\n\n"
        f"kubectl logs (tail):\n{logs}"
    )
    return False, error_summary


def generate_and_deploy(analysis, image_tag, app_name):
    load_image_into_cluster(image_tag)

    manifest_content = None
    apply_error = None
    manifest_path = f"/tmp/{app_name}-manifest.yaml"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n--- Attempt {attempt}/{MAX_ATTEMPTS}: asking LLM for manifests ---")
        manifest_content = ask_for_manifest(analysis, image_tag, app_name, manifest_content, apply_error)
        print(manifest_content)

        print(f"\n--- Attempt {attempt}: applying to cluster ---")
        success, apply_error = try_deploy(manifest_content, app_name, manifest_path)

        if success:
            print(f"Deployment succeeded on attempt {attempt}.")
            return True, manifest_content, attempt
        else:
            print(f"Deploy failed on attempt {attempt}:\n{apply_error}")

    return False, manifest_content, MAX_ATTEMPTS


if __name__ == "__main__":
    import sys
    import json
    from analyzer import clone_repo, analyze_repo
    from dockerfile_gen import generate_and_build_dockerfile

    repo_url = sys.argv[1]
    app_name = sys.argv[2] if len(sys.argv) > 2 else "agent-app"
    image_tag = f"{app_name}:v1"

    path = clone_repo(repo_url)
    analysis = analyze_repo(path)
    print("Analysis:")
    print(json.dumps(analysis, indent=2))

    build_ok, dockerfile, build_attempts = generate_and_build_dockerfile(path, analysis, image_tag)
    if not build_ok:
        print("\nStopping: Dockerfile generation/build never succeeded.")
        sys.exit(1)

    deploy_ok, manifest, deploy_attempts = generate_and_deploy(analysis, image_tag, app_name)

    print("\n=== FINAL RESULT ===")
    print(f"Dockerfile succeeded on attempt: {build_attempts}")
    print(f"Deployment succeeded: {deploy_ok} (attempt {deploy_attempts})")
    print(f"App name / label: {app_name}")
    print(f"Image: {image_tag}")
