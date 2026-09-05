import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
KEY = os.environ.get("INTERNAL_API_KEY", "")


def run(cmd):
    print("+", " ".join(cmd[:8]), "...")
    subprocess.check_call(cmd)


def main():
    run(["docker", "stop", "n8n"])
    run(["docker", "rm", "n8n"])
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "n8n",
            "-p",
            "5678:5678",
            "--add-host",
            "host.docker.internal:host-gateway",
            "-v",
            "n8n_data:/home/node/.n8n",
            "-e",
            "N8N_HOST=localhost",
            "-e",
            "N8N_PORT=5678",
            "-e",
            "N8N_PROTOCOL=http",
            "-e",
            "WEBHOOK_URL=http://localhost:5678/",
            "-e",
            "N8N_SECURE_COOKIE=false",
            "-e",
            "GENERIC_TIMEZONE=Asia/Kolkata",
            "-e",
            "N8N_BLOCK_ENV_ACCESS_IN_NODE=false",
            "-e",
            "N8N_RUNNERS_ENABLED=false",
            "-e",
            f"INTERNAL_API_KEY={KEY}",
            "docker.n8n.io/n8nio/n8n:latest",
        ]
    )
    run(
        [
            "docker",
            "cp",
            str(ROOT / "n8n" / "workflows"),
            "n8n:/tmp/workflows",
        ]
    )


if __name__ == "__main__":
    main()
