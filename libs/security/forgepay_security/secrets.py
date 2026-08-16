import base64
import hashlib
import secrets

from cryptography.fernet import Fernet


def generate_webhook_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


def _fernet(master_key: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(master_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(secret: str, master_key: str) -> str:
    return _fernet(master_key).encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str, master_key: str) -> str:
    return _fernet(master_key).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
