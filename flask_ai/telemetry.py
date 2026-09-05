import json
import logging
from typing import Any

logger = logging.getLogger("flask_ai")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_event(event: str, **fields: Any) -> None:
    safe = {k: v for k, v in fields.items() if k not in {"body", "email_body", "prompt", "api_key"}}
    logger.info("%s %s", event, json.dumps(safe, default=str))
