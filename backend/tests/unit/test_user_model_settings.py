"""Unit tests for User Model Settings — encryption, masking, validation."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


def make_client(headers=None):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers or {},
    )


def test_model_settings_mask_api_key():
    from app.core.security import encrypt_api_key

    plaintext = "sk-ant-api03-very-long-test-key-that-matches-real-format"
    secret = "test-secret-key-32-chars-minimum!!"
    encrypted = encrypt_api_key(plaintext, secret)

    assert encrypted != plaintext
    assert plaintext not in encrypted
    assert len(encrypted) > 50
    import base64
    try:
        base64.b64decode(encrypted)
    except Exception:
        pytest.fail("Encrypted key is not valid base64")


def test_encrypt_decrypt_roundtrip():
    from app.core.security import encrypt_api_key, decrypt_api_key

    secret = "test-secret-key-32-chars-minimum!!"
    plaintext = "sk-ant-api03-test-key-789012345678901234567890"
    encrypted = encrypt_api_key(plaintext, secret)
    decrypted = decrypt_api_key(encrypted, secret)
    assert decrypted == plaintext


def test_unique_ciphertext_each_encryption():
    from app.core.security import encrypt_api_key

    secret = "test-secret-key-32-chars-minimum!!"
    plaintext = "sk-ant-api03-test-key"
    enc1 = encrypt_api_key(plaintext, secret)
    enc2 = encrypt_api_key(plaintext, secret)
    assert enc1 != enc2


@pytest.mark.asyncio
async def test_add_model_settings_requires_auth():
    async with make_client() as client:
        resp = await client.post("/api/v1/users/model-settings", json={
            "provider": "openai",
            "api_key": "sk-test-key",
            "model_name": "gpt-4o",
        })
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_list_model_settings_requires_auth():
    async with make_client() as client:
        resp = await client.get("/api/v1/users/model-settings")
    assert resp.status_code in (401, 422)


def test_decrypt_with_wrong_key_raises():
    from app.core.security import encrypt_api_key, decrypt_api_key

    secret = "test-secret-key-32-chars-minimum!!"
    wrong = "wrong-secret-key-32-chars-minimum!"
    encrypted = encrypt_api_key("my-api-key", secret)
    with pytest.raises(Exception):
        decrypt_api_key(encrypted, wrong)
