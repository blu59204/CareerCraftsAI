from app.api.v1.rag import _safe_filename, _sniff_content_type


def test_sniff_rejects_declared_type_mismatch():
    # HTML/JS bytes must not pass regardless of what a client claims — this
    # is the exact bypass a security review demonstrated (content declared
    # as application/pdf but not actually a PDF).
    html_bytes = b"<html><script>alert(1)</script></html>"
    assert _sniff_content_type(html_bytes) == "text/plain"
    assert _sniff_content_type(b"%PDF-1.4 fake") == "application/pdf"
    assert _sniff_content_type(b"MZ\x90\x00fake-exe") is None
    assert _sniff_content_type(b"PK\x03\x04not-a-real-zip") is None


def test_safe_filename_strips_traversal_and_separators():
    assert _safe_filename("../../etc/passwd.txt") == "passwd.txt"
    assert _safe_filename("..\\..\\windows\\win.ini") == "win.ini"
    assert _safe_filename(None) == "upload.bin"
    assert _safe_filename("résumé (final)!!.pdf") == "r_sum_ _final___.pdf"
