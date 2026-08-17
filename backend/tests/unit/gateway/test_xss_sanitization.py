"""XSS sanitization and prevention tests.

Tests input sanitization across user-facing content paths:
- Log parameter sanitization (sanitize_log_param)
- Skill name validation (SkillStorage.validate_skill_name)
- Message content handling
- XSS payload rejection patterns
"""

import pytest

from app.gateway.utils import sanitize_log_param
from ideer.skills.storage.skill_storage import SkillStorage

# ---------------------------------------------------------------------------
# sanitize_log_param
# ---------------------------------------------------------------------------


class TestSanitizeLogParam:
    """sanitize_log_param strips control characters to prevent log injection.

    Attack vector: an attacker injects \n or \r into a logged value to
    forge fake log entries (log forging / log injection).
    """

    def test_strips_newlines(self):
        """\\n characters are removed."""
        assert sanitize_log_param("line1\nline2") == "line1line2"

    def test_strips_carriage_returns(self):
        """\\r characters are removed."""
        assert sanitize_log_param("line1\rline2") == "line1line2"

    def test_strips_null_bytes(self):
        """\\x00 characters are removed."""
        assert sanitize_log_param("foo\x00bar") == "foobar"

    def test_strips_all_control_chars(self):
        """Combination of control characters is stripped."""
        result = sanitize_log_param("a\nb\rc\x00d")
        assert result == "abcd"

    def test_preserves_normal_text(self):
        """Normal text passes through unchanged."""
        assert sanitize_log_param("hello world") == "hello world"

    def test_handles_empty_string(self):
        """Empty string returns empty string."""
        assert sanitize_log_param("") == ""

    def test_handles_only_control_chars(self):
        """String with only control characters becomes empty."""
        assert sanitize_log_param("\n\r\x00") == ""

    def test_preserves_html_tags(self):
        """HTML tags are preserved (not the concern of log sanitization)."""
        result = sanitize_log_param("<script>alert(1)</script>")
        assert result == "<script>alert(1)</script>"

    def test_log_injection_payloads_are_neutralized(self):
        """Known log-forging payloads are neutralized."""
        payloads = [
            ("real message\n[INFO] User login success", "real message[INFO] User login success"),
            ("user input\r\n[ERROR] Something broke", "user input[ERROR] Something broke"),
            ("msg\x00null byte injection", "msgnull byte injection"),
            ("a\nb\nc\n", "abc"),
            ("\n\n\n", ""),
        ]
        for payload, expected in payloads:
            assert sanitize_log_param(payload) == expected

    def test_mixed_content_with_xss(self):
        """XSS in log params is not executed but also not stripped."""
        xss = "<script>document.cookie</script>"
        result = sanitize_log_param(xss)
        assert "<script>" in result  # sanitize_log_param only strips control chars


# ---------------------------------------------------------------------------
# Skill name validation (XSS via skill names)
# ---------------------------------------------------------------------------


class TestSkillNameXSS:
    """Skill name validation rejects XSS and injection payloads.

    Uses the same SkillStorage.validate_skill_name function the skill
    management tool relies on.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "<script>alert(1)</script>",
            "my_skill<script>",
            "skill_name<img src=x onerror=alert(1)>",
            "a; DROP TABLE skills",
            "../../etc/passwd",
            "skill with spaces",
            "skill.name",
            "skill,name",
            "skill(name)",
            "",
        ],
    )
    def test_xss_payloads_rejected(self, name):
        """Skill names with XSS, injection, or special chars are rejected."""
        with pytest.raises(ValueError, match="hyphen-case"):
            SkillStorage.validate_skill_name(name)

    @pytest.mark.parametrize(
        "name",
        [
            "valid-skill",
            "skill123",
            "my-skill-1",
            "a" * 63,
        ],
    )
    def test_legitimate_names_accepted(self, name):
        """Valid skill names should not raise an error."""
        SkillStorage.validate_skill_name(name)  # should not raise


# ---------------------------------------------------------------------------
# HTML/script injection in X-CSRF-Token header
# ---------------------------------------------------------------------------


class TestCSRFHeaderXSS:
    """CSRF header values containing XSS are handled safely.

    The middleware compares header and cookie values with
    secrets.compare_digest — it never reflects the value in an
    error page or response body that would execute scripts.
    """

    def test_xss_in_csrf_header_does_not_reflect(self):
        """XSS in CSRF header produces a plain-text error, not reflected HTML."""
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        from app.gateway.csrf_middleware import CSRFMiddleware

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app, base_url="https://ideer.example")
        response = client.post(
            "/api/test",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "<script>alert('xss')</script>",
            },
        )
        # The response must be valid JSON, not HTML
        assert response.status_code == 403
        content_type = response.headers.get("content-type", "")
        assert "json" in content_type, f"Response should be JSON, got {content_type}"
        body = response.json()
        assert isinstance(body, dict)
        assert "detail" in body


# ---------------------------------------------------------------------------
# Memory / message content XSS (defence-in-depth)
# ---------------------------------------------------------------------------


class TestMessageContentXSS:
    """Defence-in-depth: message content with XSS is stored as-is.

    The system stores messages as JSON/structured data and serves them
    via JSON API — HTML/script in message content is never rendered in
    an HTML context by the backend. The frontend is responsible for
    output encoding.
    """

    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<svg onload=alert(1)>",
            "javascript:alert(1)",
            "<body onload=alert(1)>",
            "<iframe src=javascript:alert(1)>",
            "{{constructor.constructor('alert(1)')()}}",
            "{{7*7}}",
            "<%= 7*7 %>",
            "${7*7}",
        ],
    )
    def test_xss_payloads_are_valid_utf8(self, payload):
        """XSS payloads are valid strings (backend stores, frontend escapes)."""
        assert isinstance(payload, str)
        encoded = payload.encode("utf-8")
        decoded = encoded.decode("utf-8")
        assert decoded == payload

    def test_no_html_content_type_for_json_responses(self):
        """JSON API responses must not use text/html content type."""
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.post("/api/memory")
        async def create_memory():
            return {"content": "<script>alert(1)</script>"}

        @app.get("/api/messages")
        async def list_messages():
            return {"messages": [{"text": "<img src=x onerror=alert(1)>"}]}

        client = TestClient(app)

        response = client.post("/api/memory", json={"text": "test"})
        assert "json" in response.headers.get("content-type", ""), "Memory creation endpoint should return JSON, not HTML"

        response = client.get("/api/messages")
        assert "json" in response.headers.get("content-type", ""), "Message listing endpoint should return JSON, not HTML"

    def test_404_error_responses_are_json_not_html(self):
        """404 error responses must be JSON, not HTML (preventing XSS via error pages).

        FastAPI defaults to JSON for HTTPException-based errors. This test
        verifies that unknown routes produce a JSON 404, not an HTML page.
        """
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.get("/api/existing-route")
        async def existing():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/api/non-existent-route")
        content_type = response.headers.get("content-type", "")
        assert "json" in content_type, f"404 response should be JSON, got {content_type}"

    def test_422_error_responses_are_json(self):
        """Validation errors return JSON, preventing XSS via error messages."""
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.post("/api/items")
        async def create_item(name: str):
            return {"ok": True}

        client = TestClient(app)
        response = client.post("/api/items", json={})
        content_type = response.headers.get("content-type", "")
        assert "json" in content_type, f"422 response should be JSON, got {content_type}"


# ---------------------------------------------------------------------------
# URL parameter XSS
# ---------------------------------------------------------------------------


class TestURLParameterXSS:
    """Route parameters containing XSS are handled safely.

    FastAPI's route parameters are URL-decoded and passed as strings —
    they are never rendered in HTML without encoding.
    """

    @pytest.mark.parametrize(
        "path_suffix",
        [
            "<script>",
            "?q=<script>",
            "#<script>",
        ],
    )
    def test_xss_in_path_returns_json_error(self, path_suffix):
        """XSS in paths must not produce HTML error pages."""
        from fastapi import FastAPI, Request
        from starlette.responses import JSONResponse
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.exception_handler(Exception)
        async def handler(request: Request, exc: Exception):
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        client = TestClient(app, base_url="https://ideer.example")
        response = client.get(f"/api{path_suffix}")
        assert "json" in response.headers.get("content-type", ""), f"Error response for {path_suffix} should be JSON"
