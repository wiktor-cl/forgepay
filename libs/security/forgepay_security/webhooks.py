import hashlib
import hmac


def sign_webhook(secret: str, timestamp: int, body: bytes) -> str:
    signed = f"{timestamp}.".encode() + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_webhook(secret: str, signature: str, timestamp: int, body: bytes) -> bool:
    expected = sign_webhook(secret, timestamp, body)
    return hmac.compare_digest(expected, signature)
