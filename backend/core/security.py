import hmac
import hashlib
from backend.core.config import settings


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """
    Verifies the webhook signature from GitHub using the configured secret.
    """
    if not signature_header or not settings.GITHUB_WEBHOOK_SECRET:
        return False

    hash_object = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)
