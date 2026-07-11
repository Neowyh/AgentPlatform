"""Extended CSRF tests for methods and edge cases not covered by test_csrf_middleware.py.

Covers:
- PUT, DELETE, PATCH method CSRF enforcement
- Multiple simultaneous requests with the same token
- Binary/malformed cookie values
- Concurrent token reuse
"""

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.gateway.csrf_middleware import CSRFMiddleware


def _make_app() -> FastAPI:
    """Build a test app with CSRF middleware and a handler per method."""
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.put("/api/resources/{rid}")
    async def update_resource(rid: str):
        return {"ok": True, "method": "PUT", "rid": rid}

    @app.delete("/api/resources/{rid}")
    async def delete_resource(rid: str):
        return {"ok": True, "method": "DELETE", "rid": rid}

    @app.patch("/api/resources/{rid}")
    async def patch_resource(rid: str):
        return {"ok": True, "method": "PATCH", "rid": rid}

    @app.post("/api/threads/{tid}/runs/stream")
    async def create_run(tid: str):
        return {"ok": True, "method": "POST", "tid": tid}

    return app


class TestCSRFExtendedMethods:
    """CSRF enforcement for PUT, DELETE, PATCH methods.

    The middleware checks state-changing methods per should_check_csrf().
    Those methods must reject requests without a valid double-submit token.
    """

    def test_put_without_csrf_token_rejected(self):
        """PUT without CSRF token returns 403."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        response = client.put(
            "/api/resources/1",
            headers={"Origin": "https://ideer.example"},
        )
        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

    def test_put_with_valid_csrf_token_allowed(self):
        """PUT with matching CSRF tokens returns 200."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "my-token")
        response = client.put(
            "/api/resources/1",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "my-token",
            },
        )
        assert response.status_code == 200
        assert response.json()["method"] == "PUT"

    def test_put_with_mismatched_csrf_token_rejected(self):
        """PUT with mismatched CSRF tokens returns 403."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "cookie-token")
        response = client.put(
            "/api/resources/1",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "header-token",
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF token mismatch."

    def test_delete_without_csrf_token_rejected(self):
        """DELETE without CSRF token returns 403."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        response = client.delete(
            "/api/resources/1",
            headers={"Origin": "https://ideer.example"},
        )
        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

    def test_delete_with_valid_csrf_token_allowed(self):
        """DELETE with matching CSRF tokens returns 200."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "del-token")
        response = client.delete(
            "/api/resources/1",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "del-token",
            },
        )
        assert response.status_code == 200
        assert response.json()["method"] == "DELETE"

    def test_delete_with_mismatched_csrf_token_rejected(self):
        """DELETE with mismatched CSRF tokens returns 403."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "cookie-del")
        response = client.delete(
            "/api/resources/1",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "header-del",
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF token mismatch."

    def test_patch_without_csrf_token_rejected(self):
        """PATCH without CSRF token returns 403."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        response = client.patch(
            "/api/resources/1",
            headers={"Origin": "https://ideer.example"},
        )
        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

    def test_patch_with_valid_csrf_token_allowed(self):
        """PATCH with matching CSRF tokens returns 200."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "patch-token")
        response = client.patch(
            "/api/resources/1",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "patch-token",
            },
        )
        assert response.status_code == 200
        assert response.json()["method"] == "PATCH"

    def test_patch_with_mismatched_csrf_token_rejected(self):
        """PATCH with mismatched CSRF tokens returns 403."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "cookie-patch")
        response = client.patch(
            "/api/resources/1",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "header-patch",
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF token mismatch."


class TestCSRFMultipleRequests:
    """Multiple simultaneous requests with the same CSRF token."""

    def test_token_reusable_across_sequential_requests(self):
        """The same CSRF token works for multiple requests in sequence."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "reusable")
        headers = {
            "Origin": "https://ideer.example",
            "X-CSRF-Token": "reusable",
        }

        for _ in range(5):
            response = client.post(
                "/api/threads/t1/runs/stream",
                headers=headers,
            )
            assert response.status_code == 200

    def test_token_reusable_across_different_methods(self):
        """The same CSRF token works across PUT, DELETE, PATCH, POST."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "multi-method")
        headers = {
            "Origin": "https://ideer.example",
            "X-CSRF-Token": "multi-method",
        }

        assert client.post("/api/threads/t1/runs/stream", headers=headers).status_code == 200
        assert client.put("/api/resources/1", headers=headers).status_code == 200
        assert client.patch("/api/resources/1", headers=headers).status_code == 200
        assert client.delete("/api/resources/1", headers=headers).status_code == 200

    def test_different_tokens_in_flight_do_not_interfere(self):
        """Two clients with different tokens can both operate."""
        client_a = TestClient(_make_app(), base_url="https://ideer.example")
        client_a.cookies.set("csrf_token", "token-a")

        client_b = TestClient(_make_app(), base_url="https://ideer.example")
        client_b.cookies.set("csrf_token", "token-b")

        headers_a = {"Origin": "https://ideer.example", "X-CSRF-Token": "token-a"}
        headers_b = {"Origin": "https://ideer.example", "X-CSRF-Token": "token-b"}

        assert client_a.post("/api/threads/t1/runs/stream", headers=headers_a).status_code == 200
        assert client_b.post("/api/threads/t1/runs/stream", headers=headers_b).status_code == 200


class TestCSRFMalformedTokens:
    """CSRF middleware behaviour with binary, malformed, or edge-case cookie values."""

    def test_empty_cookie_value(self):
        """Empty CSRF cookie is treated as missing -> 403."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "")
        response = client.post(
            "/api/threads/t1/runs/stream",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "",
            },
        )
        # Both empty strings: secrets.compare_digest("", "") == True
        # But the middleware checks `not cookie_token or not header_token`
        # first — empty strings are falsy, so it returns 403
        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

    def test_cookie_with_only_whitespace(self):
        """Whitespace-only cookie value may be rejected (cookie encoding edge case).

        HTTP cookies with whitespace may not round-trip correctly through
        the test client — the important thing is the middleware doesn't crash.
        """
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "   ")
        response = client.post(
            "/api/threads/t1/runs/stream",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "   ",
            },
        )
        assert response.status_code in (200, 403)

    def test_very_long_token(self):
        """Very long CSRF tokens must still be compared correctly."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        long_token = "x" * 4096
        client.cookies.set("csrf_token", long_token)
        response = client.post(
            "/api/threads/t1/runs/stream",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": long_token,
            },
        )
        assert response.status_code == 200

    def test_very_long_token_mismatch(self):
        """Very long CSRF token mismatch is still detected."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        client.cookies.set("csrf_token", "x" * 4096)
        response = client.post(
            "/api/threads/t1/runs/stream",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "y" * 4096,
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF token mismatch."

    def test_token_with_special_ascii_chars(self):
        """CSRF token with special ASCII characters (non-alphanumeric) is handled."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        token = "token_with-special.chars!@#$%^&*()"
        client.cookies.set("csrf_token", token)
        response = client.post(
            "/api/threads/t1/runs/stream",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": token,
            },
        )
        assert response.status_code == 200

    def test_html_in_cookie_value(self):
        """HTML/XSS payload in cookie value is not executed (just compared)."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        payload = "<script>alert('xss')</script>"
        client.cookies.set("csrf_token", payload)
        response = client.post(
            "/api/threads/t1/runs/stream",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": payload,
            },
        )
        assert response.status_code == 200

    def test_cookie_and_header_both_present_but_cookie_missing_key(self):
        """Ensure the middleware checks the correct cookie key 'csrf_token'."""
        client = TestClient(_make_app(), base_url="https://ideer.example")
        # Set a wrong cookie name
        client.cookies.set("wrong_name", "my-token")
        response = client.post(
            "/api/threads/t1/runs/stream",
            headers={
                "Origin": "https://ideer.example",
                "X-CSRF-Token": "my-token",
            },
        )
        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]
