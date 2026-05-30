from types import SimpleNamespace


def test_apply_harness_result_sanitizes_failed_errors():
    from app.api.v1.run_utils import CLIENT_SAFE_AGENT_ERROR, apply_harness_result

    run = SimpleNamespace(
        status=None,
        output=None,
        duration_ms=None,
        completed_at=None,
    )

    output = apply_harness_result(
        run,
        {
            "status": "failed",
            "error": "provider rejected api_key=sk_live_secret",
            "duration_ms": 12,
        },
    )

    assert output == {"error": CLIENT_SAFE_AGENT_ERROR}
    assert run.output == {"error": CLIENT_SAFE_AGENT_ERROR}
    assert "sk_live_secret" not in str(run.output)
