"""Decrypt n8n Gmail OAuth only far enough to send one self-test message. Never prints tokens."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / "tmp_n8n"
TMP.mkdir(exist_ok=True)


def docker_cp(src: str, dest: str) -> None:
    subprocess.check_call(["docker", "cp", src, dest])


def decrypt_n8n(raw: str, encryption_key: str) -> dict:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import hashes, padding
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64

    payload = json.loads(raw) if raw.startswith("{") else None
    if isinstance(payload, dict) and "encrypted" not in str(payload).lower() and "access_token" in json.dumps(payload):
        return payload

    # n8n stores credentials as JSON string: {"encrypted": true, ...} or cipher blob
    data = json.loads(raw)
    if "access_token" in data or "oauthTokenData" in data:
        return data

    encrypted = data.get("data") or data.get("encryptedData") or raw
    salt = b"salt"  # n8n default
    kdf = PBKDF2HMAC(algorithm=hashes.SHA1(), length=24, salt=salt, iterations=1)
    key = kdf.derive(encryption_key.encode("utf-8"))
    blob = base64.b64decode(encrypted if isinstance(encrypted, str) else data["data"])
    iv, ciphertext = blob[:16], blob[16:]
    cipher = Cipher(algorithms.TripleDES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(64).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    return json.loads(plain.decode("utf-8"))


def main() -> None:
    docker_cp("n8n:/home/node/.n8n/config", str(TMP / "config"))
    docker_cp("n8n:/home/node/.n8n/database.sqlite", str(TMP / "database.sqlite"))
    cfg = json.loads((TMP / "config").read_text(encoding="utf-8"))
    key = cfg.get("encryptionKey") or ""
    if not key:
        print("no encryption key")
        sys.exit(1)
    con = sqlite3.connect(TMP / "database.sqlite")
    row = con.execute(
        "SELECT data FROM credentials_entity WHERE id='8KCxPfpiIW8Mx4E0'"
    ).fetchone()
    if not row:
        print("gmail credential missing")
        sys.exit(1)
    creds = decrypt_n8n(row[0], key)
    oauth = creds.get("oauthTokenData") or creds
    email = (
        creds.get("email")
        or creds.get("user")
        or (oauth.get("email") if isinstance(oauth, dict) else None)
        or ""
    )
    token = None
    if isinstance(oauth, dict):
        token = oauth.get("access_token")
        email = email or oauth.get("id_token") or ""
    print("gmail_fields", sorted(creds.keys()))
    if isinstance(oauth, dict):
        print("oauth_fields", sorted(oauth.keys()))
    print("email_present", bool(email), "token_present", bool(token))


if __name__ == "__main__":
    main()
