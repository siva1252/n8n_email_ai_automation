import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)
load_dotenv(override=True)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:2b")
OLLAMA_FALLBACK_MODEL = os.environ.get("OLLAMA_FALLBACK_MODEL", "phi3:latest")

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "open-mistral-nemo")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "").strip()
CEREBRAS_MODEL = os.environ.get("CEREBRAS_MODEL", "llama3.1-8b")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

PRIMARY_TIMEOUT = _int("AI_PRIMARY_TIMEOUT_SECONDS", 15)
FALLBACK_TIMEOUT = _int("AI_FALLBACK_TIMEOUT_SECONDS", 20)
MAX_RETRIES = _int("AI_MAX_RETRIES", 0)
MIN_CONFIDENCE = _float("AI_MIN_CONFIDENCE", 0.80)
NEGOTIATION_MAX_ROUNDS = _int("NEGOTIATION_MAX_ROUNDS", 3)
MIN_PRICE = _float("NEGOTIATION_MIN_PRICE", 4000)
TARGET_PRICE = _float("NEGOTIATION_TARGET_PRICE", 5000)
AI_MOCK = _bool("AI_MOCK", False)
USE_LOCAL_AI = _bool("USE_LOCAL_AI", False)

def _existing_dir(env_name: str, default: Path) -> Path:
    raw = os.environ.get(env_name)
    candidate = Path(raw) if raw else default
    if candidate.exists():
        return candidate
    return default


RAG_DATA_DIR = _existing_dir("RAG_DATA_DIR", ROOT / "rag_data")
VECTOR_DB_DIR = _existing_dir("VECTOR_DB_DIR", ROOT / "data" / "vector_store")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", "tfidf")

# Local model is optional and never installed by this project. APIs are the default path.
PROVIDER_CHAIN = (["ollama"] if USE_LOCAL_AI else []) + ["mistral", "groq", "cerebras", "openrouter"]
