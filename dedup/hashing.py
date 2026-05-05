import hashlib

def sha256_bytes(data: bytes) -> str:
    """Return SHA-256 hex digest of given bytes."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    return hashlib.sha256(data).hexdigest()