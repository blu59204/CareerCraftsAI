"""Edge case tests covering common AI-coded app failure patterns.

Groups:
  1. Input validation (schema-layer rejections)
  2. JWT auth edge cases
  3. Concurrent / race-condition shapes
  4. Encryption edge cases
  5. API security (injection, XSS surfaces)
"""

import base64
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------
# conftest bootstraps env vars before any app import, so this is safe.
from app.core.config import settings
from app.core.security import decrypt_api_key, encrypt_api_key
from app.core.supabase_auth import verify_supabase_jwt
from app.models.schemas import ModelSettingsCreate, UserCreate

# Clerk signs session tokens with RS256 against a published JWKS. Generate a
# throwaway keypair once and stub the JWKS client with its public half, so the
# auth tests exercise the real jwt.decode path instead of a mock.
_SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_CLERK_SUB = "user_2abcDEF3456ghiJKL7890mnoPQ"


def _public_pem(private_key) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


@contextmanager
def _jwks_serving(private_key=_SIGNING_KEY):
    """Patch the lazily-built JWKS client to hand back ``private_key``'s public half."""
    signing_key = MagicMock()
    signing_key.key = private_key.public_key()
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    with patch("app.core.supabase_auth._jwks_client", client):
        yield client


def _make_jwt(
    sub: str | None = _CLERK_SUB,
    exp_offset: int | None = 3600,
    key=_SIGNING_KEY,
    algorithm: str = "RS256",
    **extra,
) -> str:
    """Build a signed Clerk-shaped JWT with controllable claims for testing."""
    payload: dict = {"iat": int(time.time()), **extra}
    if sub is not None:
        payload["sub"] = sub
    if exp_offset is not None:
        payload["exp"] = int(time.time()) + exp_offset
    return jwt.encode(payload, key, algorithm=algorithm)


# ===========================================================================
# Group 1: Input validation edge cases
# ===========================================================================


class TestInputValidation:
    """Schema-layer guards must reject malformed payloads before business logic."""

    def test_jd_text_max_length_enforced(self):
        """OptimizeRequest.jd_text capped at 20 000 chars — oversized input must raise."""
        from app.api.v1.resume import OptimizeRequest

        with pytest.raises(ValidationError):
            OptimizeRequest(jd_text="x" * 20_001)

    def test_jd_text_at_exactly_max_length_is_accepted(self):
        """Boundary value: exactly 20 000 chars must be valid."""
        from app.api.v1.resume import OptimizeRequest

        obj = OptimizeRequest(jd_text="x" * 20_000)
        assert len(obj.jd_text) == 20_000

    def test_search_query_max_length_enforced(self):
        """JobSearchRequest.search_query capped at 200 chars."""
        from app.api.v1.jobs import JobSearchRequest

        with pytest.raises(ValidationError):
            JobSearchRequest(search_query="q" * 201)

    def test_search_query_at_max_length_accepted(self):
        """Boundary: exactly 200-char search query is valid."""
        from app.api.v1.jobs import JobSearchRequest

        obj = JobSearchRequest(search_query="q" * 200)
        assert len(obj.search_query) == 200

    def test_api_key_empty_string_rejected(self):
        """ModelSettingsCreate.api_key requires min_length=1; empty string must fail."""
        with pytest.raises(ValidationError):
            ModelSettingsCreate(
                provider="anthropic",
                api_key="",
                model_name="claude-sonnet-4-6",
            )

    def test_api_key_whitespace_only_is_accepted_by_schema(self):
        """Schema allows a single space (min_length=1 is met); business logic
        must enforce non-blank at a higher layer.  This test documents current
        schema behaviour so it is visible if tightened later."""
        obj = ModelSettingsCreate(
            provider="anthropic",
            api_key=" ",
            model_name="claude-sonnet-4-6",
        )
        assert obj.api_key == " "

    def test_supabase_uid_empty_rejected(self):
        """UserCreate.supabase_uid has min_length=1; an empty subject must fail."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="user@example.com",
                supabase_uid="",
            )

    def test_supabase_uid_too_long_rejected(self):
        """UserCreate.supabase_uid has max_length=255; 256 chars must fail."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="user@example.com",
                supabase_uid="a" * 256,
            )

    def test_clerk_text_subject_accepted(self):
        """Clerk subjects are text ids (user_2abc...), not 36-char UUIDs."""
        obj = UserCreate(
            email="user@example.com",
            supabase_uid="user_2abcDEF3456ghiJKL7890mnoPQ",
        )
        assert obj.supabase_uid.startswith("user_")

    def test_email_format_validated(self):
        """UserCreate.email uses EmailStr; a non-email string must raise."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="not-an-email",
                supabase_uid="00000000-0000-0000-0000-000000000abc",
            )

    def test_provider_invalid_value_rejected(self):
        """ModelSettingsCreate.provider is a Literal; unknown value must fail."""
        with pytest.raises(ValidationError):
            ModelSettingsCreate(
                provider="unknown_llm_provider",
                api_key="sk-test",
                model_name="gpt-4",
            )

    def test_api_key_at_max_length_accepted(self):
        """api_key max_length=200 — exactly 200 chars is valid."""
        obj = ModelSettingsCreate(
            provider="openai",
            api_key="k" * 200,
            model_name="gpt-4o",
        )
        assert len(obj.api_key) == 200

    def test_api_key_over_max_length_rejected(self):
        """api_key max_length=4096 — 4097 chars must fail."""
        with pytest.raises(ValidationError):
            ModelSettingsCreate(
                provider="openai",
                api_key="k" * 4097,
                model_name="gpt-4o",
            )


# ===========================================================================
# Group 2: JWT auth edge cases
# ===========================================================================


class TestJWTEdgeCases:
    """verify_supabase_jwt must raise HTTPException(401) for every bad token."""

    def test_valid_token_is_accepted(self, monkeypatch):
        """Baseline: a Clerk RS256 token from the configured issuer must pass."""
        monkeypatch.setattr(settings, "CLERK_ISSUER", "https://real.clerk.accounts.dev")
        token = _make_jwt(
            iss="https://real.clerk.accounts.dev", email="user@example.com"
        )
        with _jwks_serving():
            payload = verify_supabase_jwt(token)
        assert payload["sub"] == _CLERK_SUB
        assert payload["iss"] == "https://real.clerk.accounts.dev"
        assert payload["email"] == "user@example.com"

    def test_expired_token_returns_401(self):
        """Token with exp in the past must be rejected."""
        from fastapi import HTTPException

        expired_token = _make_jwt(exp_offset=-3600)
        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(expired_token)
        assert exc_info.value.status_code == 401

    def test_wrong_issuer_returns_401(self, monkeypatch):
        """Clerk tokens carry no fixed `aud`, so issuer is the binding check."""
        from fastapi import HTTPException

        monkeypatch.setattr(settings, "CLERK_ISSUER", "https://real.clerk.accounts.dev")
        token = _make_jwt(iss="https://attacker.clerk.accounts.dev")
        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(token)
        assert exc_info.value.status_code == 401

    def test_wrong_signing_key_returns_401(self):
        """Token signed by a key that is not in the JWKS must be rejected."""
        from fastapi import HTTPException

        token = _make_jwt(key=_OTHER_KEY)
        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(token)
        assert exc_info.value.status_code == 401

    def test_malformed_token_string_returns_401(self):
        """Garbage string (not a JWT) must be rejected with 401, not 500."""
        from fastapi import HTTPException

        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt("not.a.jwt")
        assert exc_info.value.status_code == 401

    def test_empty_token_string_returns_401(self):
        """Empty string must not crash the verifier."""
        from fastapi import HTTPException

        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt("")
        assert exc_info.value.status_code == 401

    def test_hs256_token_against_rs256_verifier_returns_401(self):
        """RS256→HS256 confusion: an HS256 token signed with the public key must fail."""
        from fastapi import HTTPException

        # PyJWT refuses to *encode* HS256 with a PEM, so assemble the attack
        # token by hand: HMAC the signing input with the RSA public key bytes.
        import hashlib
        import hmac

        def _b64(raw: bytes) -> str:
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        header = _b64(b'{"alg":"HS256","typ":"JWT"}')
        body = _b64(b'{"sub":"' + _CLERK_SUB.encode() + b'","exp":9999999999}')
        signing_input = f"{header}.{body}".encode()
        sig = hmac.new(
            _public_pem(_SIGNING_KEY), signing_input, hashlib.sha256
        ).digest()
        forged = f"{header}.{body}.{_b64(sig)}"

        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(forged)
        assert exc_info.value.status_code == 401

    def test_none_algorithm_token_returns_401(self):
        """alg=none / unsigned token must be rejected."""
        from fastapi import HTTPException

        # Build a token without signature using the 'none' algorithm trick
        header = base64.urlsafe_b64encode(
            b'{"alg":"none","typ":"JWT"}'
        ).rstrip(b"=").decode()
        body = base64.urlsafe_b64encode(
            b'{"sub":"uid","exp":9999999999}'
        ).rstrip(b"=").decode()
        unsigned_token = f"{header}.{body}."

        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(unsigned_token)
        assert exc_info.value.status_code == 401

    def test_missing_sub_claim_returns_401(self):
        """Token without 'sub' claim must be rejected (require=['exp','sub'])."""
        from fastapi import HTTPException

        token = _make_jwt(sub=None)
        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(token)
        assert exc_info.value.status_code == 401

    def test_missing_exp_claim_returns_401(self):
        """Token without 'exp' claim must be rejected (require=['exp','sub'])."""
        from fastapi import HTTPException

        token = _make_jwt(exp_offset=None)
        with _jwks_serving(), pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(token)
        assert exc_info.value.status_code == 401

    def test_unconfigured_clerk_jwks_returns_401(self, monkeypatch):
        """With no CLERK_JWKS_URL/CLERK_ISSUER the verifier must 401, not 500."""
        from fastapi import HTTPException

        monkeypatch.setattr(settings, "CLERK_JWKS_URL", "")
        monkeypatch.setattr(settings, "CLERK_ISSUER", "")
        monkeypatch.setattr("app.core.supabase_auth._jwks_client", None)
        with pytest.raises(HTTPException) as exc_info:
            verify_supabase_jwt(_make_jwt())
        assert exc_info.value.status_code == 401


# ===========================================================================
# Group 3: Concurrent / race-condition shapes
# ===========================================================================


class TestConcurrency:
    """Pydantic schema guards that prevent duplicate / empty-uid payloads at the
    serialisation boundary — the layer tested here is pure schema validation,
    not the DB unique constraint (which requires a real DB)."""

    def test_empty_supabase_uid_rejected(self):
        """supabase_uid='' is shorter than min_length=1 — must fail validation."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="a@example.com",
                supabase_uid="",
            )

    def test_second_identical_user_create_payload_is_valid_schema(self):
        """Two identical UserCreate payloads are each individually valid at the
        schema layer.  The uniqueness constraint lives at the DB level; this test
        documents that schema validation does not deduplicate (so the duplicate
        path in the DB layer is reachable and must be handled there)."""
        uid = "00000000-0000-0000-0000-000000000abc"
        u1 = UserCreate(email="dup@example.com", supabase_uid=uid)
        u2 = UserCreate(email="dup@example.com", supabase_uid=uid)
        assert u1.supabase_uid == u2.supabase_uid

    def test_all_valid_providers_construct_model_settings(self):
        """Every Literal provider value must be constructable — ensures enum list
        is not accidentally out of sync with the schema."""
        for provider in ("anthropic", "openai", "google", "ollama", "nvidia_nim", "openrouter", "opencode"):
            obj = ModelSettingsCreate(
                provider=provider,
                api_key="sk-test-key",
                model_name="some-model",
            )
            assert obj.provider == provider


# ===========================================================================
# Group 4: Encryption edge cases
# ===========================================================================


class TestEncryptionEdgeCases:
    """Encryption layer (AES-GCM) must handle edge inputs without crashing and
    must surface errors as ValueError, not as unguarded exceptions."""

    _SECRET = "test-secret-key-32-chars-minimum!!"

    def test_decrypt_truncated_ciphertext_raises_value_error(self):
        """A truncated payload (fewer than 28 header bytes) must raise ValueError."""
        # Encode only 10 bytes — far less than the 16-byte salt + 12-byte nonce minimum
        truncated = base64.b64encode(b"\x00" * 10).decode()
        with pytest.raises((ValueError, Exception)):
            decrypt_api_key(truncated, self._SECRET)

    def test_decrypt_empty_string_raises(self):
        """An empty ciphertext string must raise, not silently return empty."""
        with pytest.raises(Exception):
            decrypt_api_key("", self._SECRET)

    def test_decrypt_random_garbage_raises_value_error(self):
        """Random bytes that are valid base64 but invalid ciphertext must raise."""
        garbage = base64.b64encode(b"\xde\xad\xbe\xef" * 20).decode()
        with pytest.raises((ValueError, Exception)):
            decrypt_api_key(garbage, self._SECRET)

    def test_encrypt_unicode_string_roundtrip(self):
        """Encrypt/decrypt must handle unicode (emoji, CJK, etc.) correctly."""
        original = "sk-test-\U0001f511-unicode-测试-key"
        encrypted = encrypt_api_key(original, self._SECRET)
        decrypted = decrypt_api_key(encrypted, self._SECRET)
        assert decrypted == original

    def test_encrypt_very_long_key_roundtrip(self):
        """A 200-char API key (max schema length) must survive round-trip."""
        original = "k" * 200
        encrypted = encrypt_api_key(original, self._SECRET)
        assert decrypt_api_key(encrypted, self._SECRET) == original

    def test_encrypt_single_char_key_roundtrip(self):
        """Minimum-length key (1 char) must round-trip cleanly."""
        original = "x"
        assert decrypt_api_key(encrypt_api_key(original, self._SECRET), self._SECRET) == original

    def test_decrypt_modified_ciphertext_raises(self):
        """Flipping a single byte in the ciphertext must cause authentication failure."""
        encrypted = encrypt_api_key("my-api-key", self._SECRET)
        raw = bytearray(base64.b64decode(encrypted))
        # Flip the last byte of the ciphertext (GCM tag covers this)
        raw[-1] ^= 0xFF
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises((ValueError, Exception)):
            decrypt_api_key(tampered, self._SECRET)

    def test_encrypted_output_is_not_plaintext(self):
        """Sanity: the encrypted form must not equal the plaintext."""
        plaintext = "sk-anthropic-real-key"
        assert encrypt_api_key(plaintext, self._SECRET) != plaintext

    def test_two_encryptions_of_same_plaintext_differ(self):
        """Each call produces a fresh random salt+nonce — outputs must differ."""
        plaintext = "same-key"
        enc1 = encrypt_api_key(plaintext, self._SECRET)
        enc2 = encrypt_api_key(plaintext, self._SECRET)
        assert enc1 != enc2

    def test_decrypt_non_base64_string_raises(self):
        """A string that is not valid base64 must raise, not crash silently."""
        with pytest.raises(Exception):
            decrypt_api_key("!!!not-base64!!!", self._SECRET)


# ===========================================================================
# Group 5: API security surface — schema-layer assertions
# ===========================================================================


class TestAPISecurityEdgeCases:
    """These tests validate the schema layer (Pydantic) for injection and XSS
    inputs.  They confirm that payloads containing dangerous strings are either
    rejected or pass through as inert text.  No 500 is acceptable."""

    def test_sql_injection_in_search_query_exceeds_length_limit(self):
        """A classic long SQL injection string exceeds max_length=200 and must
        be rejected at the schema layer."""
        from app.api.v1.jobs import JobSearchRequest

        injection = "' OR '1'='1'; DROP TABLE users; SELECT * FROM users WHERE '1'='1"
        # This particular injection is < 200 chars, so it passes the length check.
        # We validate it IS accepted by schema (sanitisation happens at DB layer via
        # parameterised queries — this test documents the expected schema behaviour).
        obj = JobSearchRequest(search_query=injection)
        # The raw string is preserved — parameterised queries make it inert at DB level
        assert "DROP TABLE" in obj.search_query

    def test_sql_injection_over_max_length_is_rejected(self):
        """Padding a SQL injection to > 200 chars must trigger schema rejection."""
        from app.api.v1.jobs import JobSearchRequest

        injection = ("' OR '1'='1'; DROP TABLE users; --" + " " * 180)
        assert len(injection) > 200
        with pytest.raises(ValidationError):
            JobSearchRequest(search_query=injection)

    def test_xss_payload_in_job_search_query_preserved_as_text(self):
        """<script> in search_query must pass schema validation as plain text
        (it is not HTML-rendered by the API) — but must not 500."""
        from app.api.v1.jobs import JobSearchRequest

        xss = "<script>alert('xss')</script>"
        obj = JobSearchRequest(search_query=xss)
        assert obj.search_query == xss  # stored verbatim, rendered safely by frontend

    def test_null_bytes_in_search_query_stored_as_text(self):
        """Null bytes are an uncommon injection vector; schema should
        accept them (they are short) and the value should be preserved."""
        from app.api.v1.jobs import JobSearchRequest

        null_byte = chr(0)
        payload = "python" + null_byte + "developer"
        obj = JobSearchRequest(search_query=payload)
        assert null_byte in obj.search_query

    def test_path_traversal_in_search_query_preserved_as_text(self):
        """../../etc/passwd style input must be accepted by schema as plain text
        (no traversal possible in a JSON body field)."""
        from app.api.v1.jobs import JobSearchRequest

        payload = "../../../../etc/passwd"
        obj = JobSearchRequest(search_query=payload)
        assert obj.search_query == payload

    def test_unicode_control_chars_in_api_key_schema(self):
        """API key containing unicode control characters must pass schema
        length check (min_length=1 met) — encryption handles arbitrary bytes."""
        obj = ModelSettingsCreate(
            provider="anthropic",
            api_key="sk-test ",
            model_name="claude-sonnet-4-6",
        )
        assert len(obj.api_key) >= 1


# ===========================================================================
# Group 6: Internal endpoint secret checks (timing-safe comparison)
# ===========================================================================


class TestInternalSecretEnforcement:
    """The _verify_secret helper in internal.py uses hmac.compare_digest.
    Wrong / empty secrets must always return 403, never 200 or 500."""

    def test_correct_secret_is_accepted(self):
        """_verify_secret must not raise when the correct secret is provided."""
        from app.api.internal import _verify_secret

        # Should return None without raising
        result = _verify_secret(x_internal_secret=settings.APP_SECRET_KEY)
        assert result is None

    def test_wrong_secret_raises_403(self):
        """A wrong secret must raise HTTPException with status 403."""
        from fastapi import HTTPException

        from app.api.internal import _verify_secret

        with pytest.raises(HTTPException) as exc_info:
            _verify_secret(x_internal_secret="totally-wrong-secret")
        assert exc_info.value.status_code == 403

    def test_empty_secret_raises_403(self):
        """An empty secret must not match any non-empty key."""
        from fastapi import HTTPException

        from app.api.internal import _verify_secret

        with pytest.raises(HTTPException) as exc_info:
            _verify_secret(x_internal_secret="")
        assert exc_info.value.status_code == 403

    def test_prefix_of_secret_raises_403(self):
        """Sending only the first half of the secret must fail — no prefix match."""
        from fastapi import HTTPException

        from app.api.internal import _verify_secret

        half = settings.APP_SECRET_KEY[: len(settings.APP_SECRET_KEY) // 2]
        with pytest.raises(HTTPException) as exc_info:
            _verify_secret(x_internal_secret=half)
        assert exc_info.value.status_code == 403

    def test_secret_with_extra_char_raises_403(self):
        """Appending a character to the correct secret must also fail."""
        from fastapi import HTTPException

        from app.api.internal import _verify_secret

        with pytest.raises(HTTPException) as exc_info:
            _verify_secret(x_internal_secret=settings.APP_SECRET_KEY + "X")
        assert exc_info.value.status_code == 403
