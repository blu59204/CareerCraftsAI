import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def derive_key(secret: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(secret.encode())


def encrypt_api_key(plaintext: str, app_secret: str) -> str:
    """AES-256-GCM encrypt with PBKDF2-HMAC-SHA256 key derivation.

    Returns a base64-encoded payload containing:
      - First 16 bytes: unique salt
      - Next 12 bytes: nonce
      - Remainder: ciphertext + 16-byte GCM tag
    """
    salt = os.urandom(16)
    key = derive_key(app_secret, salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    payload = salt + nonce + ciphertext
    return base64.b64encode(payload).decode()


def decrypt_api_key(encrypted: str, app_secret: str) -> str:
    """Reverse of encrypt_api_key. Raises ValueError on corruption or wrong key."""
    payload = base64.b64decode(encrypted.encode())
    if len(payload) < 28:  # salt(16) + nonce(12) minimum
        raise ValueError("Decryption failed — ciphertext too short")
    salt = payload[:16]
    nonce = payload[16:28]
    ciphertext = payload[28:]
    key = derive_key(app_secret, salt)
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError("Decryption failed — ciphertext corrupted or wrong key") from exc
    return plaintext.decode()


def mask_api_key(key: str) -> str:
    """Return a masked version safe for logging/display. e.g. 'sk-ant-api0...****'"""
    if not key:
        return ""
    if len(key) <= 14:
        return key[:4] + "****"
    return key[:14] + "****"
