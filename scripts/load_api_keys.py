"""Load API keys from creditinals.md into .env without printing secrets."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
creds = (ROOT / "creditinals.md").read_text(encoding="utf-8")
env_path = ROOT / ".env"
text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""

pairs = {
    "MISTRAL_API_KEY": re.search(r"mistral_api_key\s*=\s*(\S+)", creds, re.I),
    "GROQ_API_KEY": re.search(r"groq\s*=\s*(\S+)", creds, re.I),
    "CEREBRAS_API_KEY": re.search(r"cerebras\s*=\s*(\S+)", creds, re.I),
    "OPENROUTER_API_KEY": re.search(r"openrouter\s*=\s*(\S+)", creds, re.I),
}


def upsert(src: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    line = f"{key}={value}"
    if pattern.search(src):
        return pattern.sub(line, src)
    return src.rstrip() + "\n" + line + "\n"


for key, match in pairs.items():
    if not match:
        raise SystemExit(f"missing {key}")
    text = upsert(text, key, match.group(1).strip())

text = upsert(text, "USE_LOCAL_AI", "false")
text = upsert(text, "AI_MOCK", "false")
text = upsert(text, "OPENROUTER_MODEL", "openrouter/free")
env_path.write_text(text, encoding="utf-8")
print("updated .env keys:", ", ".join(pairs))
