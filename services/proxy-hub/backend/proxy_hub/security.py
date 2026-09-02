"""Opaque token, request-integrity, and ETag helpers."""

from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe


def new_token(bytes_of_entropy: int = 32) -> str:
    """Create an opaque URL-safe token."""
    return token_urlsafe(bytes_of_entropy)


def digest_token(token: str) -> str:
    """Hash an opaque credential before persistence."""
    return sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, digest: str) -> bool:
    """Compare an opaque token to its stored digest."""
    return compare_digest(digest_token(token), digest)


def resource_etag(resource_type: str, resource_id: str, version: int) -> str:
    """Build a strong ETag for one control-plane resource version."""
    return f'"{resource_type}:{resource_id}:{version}"'
