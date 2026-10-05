import os
import json
import subprocess
import tempfile


def clone_repo(repo_url):
    """Clone the repo into a temp directory and return the local path."""
    tmp_dir = tempfile.mkdtemp(prefix="agent-repo-")
    subprocess.run(["git", "clone", "--depth", "1", repo_url, tmp_dir], check=True)
    return tmp_dir


def analyze_repo(repo_path):
    """Inspect the repo's files and return a structured summary of its stack."""
    files = os.listdir(repo_path)
    summary = {
        "language": None,
        "framework": None,
        "entry_point": None,
        "port_guess": None,
        "dependency_file": None,
        "has_dockerfile": "Dockerfile" in files,
        "top_level_files": files,
    }

    if "package.json" in files:
        summary["language"] = "node"
        summary["dependency_file"] = "package.json"
        with open(os.path.join(repo_path, "package.json")) as f:
            pkg = json.load(f)
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "express" in deps:
            summary["framework"] = "express"
        elif "next" in deps:
            summary["framework"] = "next.js"
        summary["entry_point"] = pkg.get("main", "index.js")
        scripts = pkg.get("scripts", {})
        summary["start_script"] = scripts.get("start")

    elif "requirements.txt" in files or "pyproject.toml" in files:
        summary["language"] = "python"
        summary["dependency_file"] = "requirements.txt" if "requirements.txt" in files else "pyproject.toml"
        reqs = ""
        if "requirements.txt" in files:
            with open(os.path.join(repo_path, "requirements.txt")) as f:
                reqs = f.read().lower()
        if "fastapi" in reqs:
            summary["framework"] = "fastapi"
            summary["port_guess"] = 8000
        elif "flask" in reqs:
            summary["framework"] = "flask"
            summary["port_guess"] = 5000
        elif "django" in reqs:
            summary["framework"] = "django"
            summary["port_guess"] = 8000
        for candidate in ["main.py", "app.py", "manage.py"]:
            if candidate in files:
                summary["entry_point"] = candidate
                break

    return summary


if __name__ == "__main__":
    import sys
    repo_url = sys.argv[1]
    path = clone_repo(repo_url)
    result = analyze_repo(path)
    result["local_path"] = path
    print(json.dumps(result, indent=2))
