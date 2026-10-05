"""
Autonomous DevOps Agent — CLI entry point.

Given a repo URL, this analyzes the repo, generates a working Dockerfile
(retrying with build/runtime error feedback), then generates and applies
Kubernetes manifests (retrying with deploy error feedback), and prints a
clean summary of what happened at each stage.
"""
import sys
import time
import argparse

from analyzer import clone_repo, analyze_repo
from dockerfile_gen import generate_and_build_dockerfile
from k8s_gen import generate_and_deploy


def banner(text):
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Autonomous DevOps Agent")
    parser.add_argument("repo_url", help="GitHub repo URL to onboard")
    parser.add_argument("app_name", nargs="?", default="agent-app",
                         help="Name to use for the image and k8s resources")
    parser.add_argument("--quiet", action="store_true",
                         help="Hide generated file contents, show only step results")
    args = parser.parse_args()

    start_time = time.time()
    image_tag = f"{args.app_name}:v1"

    banner(f"STEP 1/4: Cloning and analyzing {args.repo_url}")
    path = clone_repo(args.repo_url)
    analysis = analyze_repo(path)
    print(f"Language:        {analysis.get('language')}")
    print(f"Framework:       {analysis.get('framework')}")
    print(f"Entry point:     {analysis.get('entry_point')}")
    print(f"Dependency file: {analysis.get('dependency_file')}")
    print(f"Guessed port:    {analysis.get('port_guess')}")

    if not analysis.get("language"):
        print("\nCould not confidently detect the stack for this repo. Stopping.")
        print("This agent currently supports single-service Python (Flask/FastAPI/Django) "
              "and Node repos with the app at the repo root.")
        sys.exit(1)

    banner("STEP 2/4: Generating and building Dockerfile")
    build_ok, dockerfile, build_attempts = generate_and_build_dockerfile(
        path, analysis, image_tag
    )
    if not args.quiet:
        print("\nFinal Dockerfile:\n" + dockerfile)
    if not build_ok:
        banner("RESULT: FAILED at Dockerfile stage")
        print(f"Gave up after {build_attempts} attempts.")
        sys.exit(1)
    print(f"\nBuild succeeded (attempt {build_attempts}/3), runtime check passed.")

    banner("STEP 3/4: Generating and applying Kubernetes manifests")
    deploy_ok, manifest, deploy_attempts = generate_and_deploy(
        analysis, image_tag, args.app_name
    )
    if not args.quiet:
        print("\nFinal manifest:\n" + manifest)
    if not deploy_ok:
        banner("RESULT: FAILED at deployment stage")
        print(f"Dockerfile succeeded, but deployment failed after {deploy_attempts} attempts.")
        sys.exit(1)

    elapsed = time.time() - start_time

    import subprocess
    svc_port_result = subprocess.run(
        ["kubectl", "get", "service", args.app_name,
         "-o", "jsonpath={.spec.ports[0].port}"],
        capture_output=True, text=True,
    )
    actual_service_port = svc_port_result.stdout.strip() or "80"

    banner("RESULT: SUCCESS")
    print(f"Repo:               {args.repo_url}")
    print(f"Stack detected:     {analysis.get('language')} / {analysis.get('framework')}")
    print(f"Dockerfile attempts:{build_attempts}/3")
    print(f"Deploy attempts:    {deploy_attempts}/3")
    print(f"Total time:         {elapsed:.0f}s")
    print(f"\nCheck it yourself:")
    print(f"  kubectl get pods -l app={args.app_name}")
    print(f"  kubectl port-forward svc/{args.app_name} 8888:{actual_service_port}")
    print(f"  curl http://localhost:8888/")
    print(f"\nClean up when done:")
    print(f"  kubectl delete deployment,service {args.app_name}")

if __name__ == "__main__":
    main()
