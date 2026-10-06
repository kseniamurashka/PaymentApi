import hashlib
import hmac


def verify_signature(
    body: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    if signature is None:
        return False

    expected_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected_signature.encode("utf-8"),
        signature.encode("utf-8"),
    )
