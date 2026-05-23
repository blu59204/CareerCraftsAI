import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def derive_key(secret: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(secret.encode())


def encrypt_api_key(plaintext: str, app_secret: str) -> str:
    salt = os.urandom(16)
    key = derive_key(app_secret, salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    payload = salt + nonce + ciphertext
    return base64.b64encode(payload).decode()


def decrypt_api_key(encrypted: str, app_secret: str) -> str:
    payload = base64.b64decode(encrypted.encode())
    salt = payload[:16]
    nonce = payload[16:28]
    ciphertext = payload[28:]
    key = derive_key(app_secret, salt)
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Decryption failed — ciphertext corrupted or wrong key")
    return plaintext.decode()
