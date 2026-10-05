import os
import subprocess
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-120b"
MAX_ATTEMPTS = 3


def build_prompt(analysis, previous_dockerfile=None, build_error=None):
    base = (
        "You are a DevOps assistant that writes production-reasonable Dockerfiles. "
        "Given this analysis of a repository, write a complete, working Dockerfile.\n\n"
        f"Language: {analysis.get('language')}\n"
        f"Framework: {analysis.get('framework')}\n"
        f"Entry point: {analysis.get('entry_point')}\n"
        f"Dependency file: {analysis.get('dependency_file')}\n"
        f"Guessed port: {analysis.get('port_guess')}\n"
        f"Top-level files: {analysis.get('top_level_files')}\n\n"
        "Rules: respond with ONLY the Dockerfile content, no explanation, no markdown "
        "code fences, no commentary. The app must listen on 0.0.0.0, not 127.0.0.1. "
        "Use a slim base image. Install dependencies before copying the rest of the code "
        "so Docker layer caching works."
    )
    if previous_dockerfile and build_error:
        base += (
            "\n\nYour previous attempt failed to build. Here is what you wrote:\n"
            f"{previous_dockerfile}\n\n"
            f"Here is the build error:\n{build_error}\n\n"
            "Fix the Dockerfile and respond with ONLY the corrected Dockerfile content."
        )
    return base


def ask_for_dockerfile(analysis, previous_dockerfile=None, build_error=None):
    prompt = build_prompt(analysis, previous_dockerfile, build_error)
    response = groq_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content.strip()
    # Strip markdown fences if the model added them despite instructions
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return content


def try_build(repo_path, dockerfile_content, image_tag):
    dockerfile_path = os.path.join(repo_path, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)

    result = subprocess.run(
        ["docker", "build", "-t", image_tag, repo_path],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        return False, result.stderr[-2000:]

    # Build succeeded, but that doesn't mean the app actually runs.
    # Start it briefly and check it's still alive — catches apps with no
    # server start call, wrong host binding, immediate crashes, etc.
    container_name = f"agent-runtime-check-{os.getpid()}"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    run_result = subprocess.run(
        ["docker", "run", "-d", "--name", container_name, image_tag],
        capture_output=True,
        text=True,
    )
    if run_result.returncode != 0:
        return False, f"Container failed to start:\n{run_result.stderr[-1000:]}"

    import time
    time.sleep(4)  # give it a moment to crash if it's going to

    inspect = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
        capture_output=True, text=True,
    )
    status = inspect.stdout.strip()

    logs = subprocess.run(
        ["docker", "logs", container_name],
        capture_output=True, text=True,
    ).stdout[-1000:]

    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    if status != "running":
        return False, (
            f"Image built successfully, but the container exited instead of "
            f"staying up (status: {status}). This usually means the app never "
            f"starts a server (missing app.run()/listen call) or crashes on "
            f"startup. Container logs:\n{logs}"
        )

    return True, None

def generate_and_build_dockerfile(repo_path, analysis, image_tag):
    """Main loop: ask the LLM, try to build, retry with error context if it fails."""
    dockerfile_content = None
    build_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n--- Attempt {attempt}/{MAX_ATTEMPTS}: asking LLM for a Dockerfile ---")
        dockerfile_content = ask_for_dockerfile(analysis, dockerfile_content, build_error)
        print(dockerfile_content)

        print(f"\n--- Attempt {attempt}: trying to build ---")
        success, build_error = try_build(repo_path, dockerfile_content, image_tag)

        if success:
            print(f"Build succeeded on attempt {attempt}.")
            return True, dockerfile_content, attempt
        else:
            print(f"Build failed on attempt {attempt}:\n{build_error}")

    return False, dockerfile_content, MAX_ATTEMPTS


if __name__ == "__main__":
    import sys
    import json
    from analyzer import clone_repo, analyze_repo

    repo_url = sys.argv[1]
    image_tag = sys.argv[2] if len(sys.argv) > 2 else "agent-built-app:v1"

    path = clone_repo(repo_url)
    analysis = analyze_repo(path)
    print("Analysis:")
    print(json.dumps(analysis, indent=2))

    success, dockerfile, attempts = generate_and_build_dockerfile(path, analysis, image_tag)

    print("\n=== RESULT ===")
    print(f"Success: {success}")
    print(f"Attempts used: {attempts}")
    print(f"Image tag: {image_tag}")
    print(f"Repo path: {path}")
