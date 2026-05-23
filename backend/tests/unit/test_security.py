import pytest

from app.core.security import decrypt_api_key, derive_key, encrypt_api_key


def test_encrypt_decrypt_roundtrip():
    secret = "test-secret-key-32-chars-minimum!!"
    plaintext = "sk-anthropic-key-abc123"
    encrypted = encrypt_api_key(plaintext, secret)
    assert encrypted != plaintext
    decrypted = decrypt_api_key(encrypted, secret)
    assert decrypted == plaintext


def test_encrypt_produces_different_ciphertext_each_time():
    secret = "test-secret-key-32-chars-minimum!!"
    plaintext = "sk-test-key"
    enc1 = encrypt_api_key(plaintext, secret)
    enc2 = encrypt_api_key(plaintext, secret)
    assert enc1 != enc2


def test_decrypt_wrong_key_raises():
    secret = "test-secret-key-32-chars-minimum!!"
    wrong = "wrong-secret-key-32-chars-minimum!"
    encrypted = encrypt_api_key("my-api-key", secret)
    with pytest.raises(Exception):
        decrypt_api_key(encrypted, wrong)


def test_derive_key_deterministic():
    key1 = derive_key("password", b"salt1234")
    key2 = derive_key("password", b"salt1234")
    assert key1 == key2


def test_derive_key_different_salts_differ():
    key1 = derive_key("password", b"salt1234")
    key2 = derive_key("password", b"salt5678")
    assert key1 != key2
