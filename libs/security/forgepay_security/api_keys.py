import hashlib
import hmac
import secrets


def generate_api_key(live: bool = False) -> tuple[str, str]:
    prefix = "fg_live" if live else "fg_test"
    raw = f"{prefix}_{secrets.token_urlsafe(32)}"
    return raw, hash_secret(raw)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(secret: str, digest: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), digest)
