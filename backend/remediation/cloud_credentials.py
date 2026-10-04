from __future__ import annotations

import json
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    key = os.getenv("CLOUD_CREDENTIALS_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("CLOUD_CREDENTIALS_ENCRYPTION_KEY must be configured before connecting a cloud account")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("CLOUD_CREDENTIALS_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt_cloud_credentials(credentials: dict) -> str:
    serialized = json.dumps(credentials, separators=(",", ":"), sort_keys=True)
    return _fernet().encrypt(serialized.encode("utf-8")).decode("ascii")


def decrypt_cloud_credentials(ciphertext: str | None) -> dict:
    if not ciphertext:
        raise RuntimeError("No encrypted cloud credentials are stored for this account")
    try:
        decrypted = _fernet().decrypt(ciphertext.encode("ascii"))
        credentials = json.loads(decrypted.decode("utf-8"))
    except (InvalidToken, UnicodeEncodeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Cloud credentials cannot be decrypted; reconnect the account") from exc
    if not isinstance(credentials, dict):
        raise RuntimeError("Stored cloud credentials have an invalid format")
    return credentials