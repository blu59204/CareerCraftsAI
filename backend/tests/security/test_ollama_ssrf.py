"""Regression test for pentest finding vuln-0001: authenticated SSRF via an
unvalidated `ollama_url` in model settings. The server fetches this URL
directly (model_router, rag_service, llm_gateway, browser_control_service),
so it must be rejected at the single input path rather than trusted."""

import pytest
from pydantic import ValidationError

from app.models.schemas import ModelSettingsCreate

SSRF_PAYLOADS = [
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    "http://127.0.0.1:80",  # loopback
    "http://127.0.0.1:6379",  # loopback, another port
    "http://172.17.0.1:80",  # docker bridge gateway
    "http://attacker.example/ssrf-ollama",  # arbitrary external host
    "http://evil.com@127.0.0.1:11434",  # userinfo bypass attempt
    "file:///etc/passwd",  # non-http(s) scheme
    "gopher://127.0.0.1:6379/_x",  # non-http(s) scheme
    "http://[::1]:6379",  # loopback, wrong port on an allow-listed host
]

ALLOWED = ["http://localhost:11434", "http://127.0.0.1:11434", None]


@pytest.mark.parametrize("url", SSRF_PAYLOADS)
def test_ollama_url_rejects_ssrf_payloads(url):
    with pytest.raises(ValidationError):
        ModelSettingsCreate(provider="ollama", api_key="x", model_name="m", ollama_url=url)


@pytest.mark.parametrize("url", ALLOWED)
def test_ollama_url_accepts_allow_listed_hosts(url):
    settings = ModelSettingsCreate(provider="ollama", api_key="x", model_name="m", ollama_url=url)
    assert settings.ollama_url == url


def test_operator_allowlist_is_configurable(monkeypatch):
    """OLLAMA_ALLOWED_HOSTS lets an operator run Ollama on another box —
    still scheme/credential/IP-class checked, not a blanket bypass."""
    monkeypatch.setenv("OLLAMA_ALLOWED_HOSTS", "gpu-box.internal:11434")

    ModelSettingsCreate(
        provider="ollama", api_key="x", model_name="m", ollama_url="http://gpu-box.internal:11434"
    )
    with pytest.raises(ValidationError):
        ModelSettingsCreate(
            provider="ollama", api_key="x", model_name="m", ollama_url="http://127.0.0.1:80"
        )


def test_other_providers_are_unaffected():
    """The validator only runs on ollama_url, which non-ollama providers leave unset."""
    settings = ModelSettingsCreate(provider="openai", api_key="sk-x", model_name="gpt-4o")
    assert settings.ollama_url is None
