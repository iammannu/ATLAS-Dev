"""Run Python unit tests inside a restricted Docker container."""

import argparse
import subprocess
from pathlib import Path


def run_tests(workspace="."):
    root = Path(workspace).resolve(strict=True)

    if not root.is_dir():
        raise ValueError("Workspace must be a directory")

    command = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "512m",
        "--cpus", "1",
        "--pids-limit", "128",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--mount", f"type=bind,src={root},dst=/workspace,readonly",
        "--workdir", "/workspace",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "PYTHONPATH=/workspace",
        "python:3.14-slim",
        "python", "-m", "unittest",
        "discover", "-s", "tests", "-v",
    ]

    print("Running isolated tests...", flush=True)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("Test timeout exceeded.")
        return False

    print(result.stdout)
    print(result.stderr)

    if result.returncode == 0:
        print("PASS: All isolated tests passed.")
        return True

    print("FAIL: Isolated tests did not pass.")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", nargs="?", default=".")
    args = parser.parse_args()

    raise SystemExit(0 if run_tests(args.workspace) else 1)


if __name__ == "__main__":
    main()
