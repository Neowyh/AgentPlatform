"""Extra coverage tests for credential_loader.py missed lines.

Targets: 31, 46, 63, 70, 83-85, 95-97, 101-103, 111, 118-125, 132-133,
         143-144, 172-190, 203, 206, 211-212
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

from ideer.models.credential_loader import (
    ClaudeCodeCredential,
    _credential_from_direct_token,
    _extract_claude_code_credential,
    _home_dir,
    _iter_claude_code_credential_paths,
    _load_json_file,
    _read_secret_from_file_descriptor,
    _resolve_credential_path,
    is_oauth_token,
    load_claude_code_credential,
    load_codex_cli_credential,
)

# --- Line 31: is_oauth_token with non-string ---


def test_is_oauth_token_non_string():
    """Line 31: Returns False for non-string input."""
    assert is_oauth_token(123) is False
    assert is_oauth_token(None) is False
    assert is_oauth_token([]) is False


def test_is_oauth_token_string_with_marker():
    """Returns True for string containing sk-ant-oat."""
    assert is_oauth_token("sk-ant-oat01-abc") is True


def test_is_oauth_token_string_without_marker():
    """Returns False for string without sk-ant-oat."""
    assert is_oauth_token("regular-api-key") is False


# --- Line 46: ClaudeCodeCredential.is_expired when expires_at <= 0 ---


def test_credential_not_expired_when_expires_at_zero():
    """Line 46: is_expired returns False when expires_at <= 0."""
    cred = ClaudeCodeCredential(access_token="tok", expires_at=0)
    assert cred.is_expired is False


def test_credential_not_expired_when_expires_at_negative():
    """Line 46: is_expired returns False when expires_at is negative."""
    cred = ClaudeCodeCredential(access_token="tok", expires_at=-100)
    assert cred.is_expired is False


def test_credential_expired_when_past():
    """is_expired returns True when token is expired."""
    cred = ClaudeCodeCredential(access_token="tok", expires_at=int(time.time() * 1000) - 120_000)
    assert cred.is_expired is True


def test_credential_not_expired_when_future():
    """is_expired returns False when token is not expired."""
    cred = ClaudeCodeCredential(access_token="tok", expires_at=int(time.time() * 1000) + 3600_000)
    assert cred.is_expired is False


# --- Line 63: _home_dir with no HOME ---


def test_home_dir_falls_back_to_path_home(monkeypatch):
    """Line 63: Falls back to Path.home() when HOME is not set."""
    monkeypatch.delenv("HOME", raising=False)
    result = _home_dir()
    assert isinstance(result, Path)


def test_home_dir_uses_home_env(monkeypatch, tmp_path):
    """Uses HOME env var when set."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = _home_dir()
    assert result == tmp_path


# --- Line 70: _load_json_file with directory ---


def test_load_json_file_returns_none_for_directory(tmp_path):
    """Line 70: Returns None when path is a directory."""
    result = _load_json_file(tmp_path, "test")
    assert result is None


def test_load_json_file_returns_none_for_missing(tmp_path):
    """Returns None for non-existent file."""
    result = _load_json_file(tmp_path / "missing.json", "test")
    assert result is None


# --- Lines 83-85: _load_json_file JSON decode error ---


def test_load_json_file_returns_none_for_invalid_json(tmp_path):
    """Lines 83-85: Returns None for invalid JSON."""
    bad = tmp_path / "bad.json"
    bad.write_text("not json {{{")
    result = _load_json_file(bad, "test")
    assert result is None


# --- Lines 95-97: _read_secret_from_file_descriptor with invalid fd ---


def test_read_secret_from_fd_returns_none_for_non_int(monkeypatch):
    """Lines 95-97: Returns None when env var is not an integer."""
    monkeypatch.setenv("TEST_FD_VAR", "not_a_number")
    result = _read_secret_from_file_descriptor("TEST_FD_VAR")
    assert result is None


def test_read_secret_from_fd_returns_none_when_unset(monkeypatch):
    """Returns None when env var is not set."""
    monkeypatch.delenv("TEST_FD_VAR", raising=False)
    result = _read_secret_from_file_descriptor("TEST_FD_VAR")
    assert result is None


# --- Lines 101-103: _read_secret_from_file_descriptor OSError ---


def test_read_secret_from_fd_returns_none_on_oserror(monkeypatch):
    """Lines 101-103: Returns None on OSError."""
    monkeypatch.setenv("TEST_FD_VAR", "99999")
    with patch("os.read", side_effect=OSError("bad fd")):
        result = _read_secret_from_file_descriptor("TEST_FD_VAR")
    assert result is None


# --- Line 111: _credential_from_direct_token empty ---


def test_credential_from_direct_token_empty():
    """Line 111: Returns None for empty/whitespace token."""
    assert _credential_from_direct_token("", "source") is None
    assert _credential_from_direct_token("   ", "source") is None


def test_credential_from_direct_token_valid():
    """Returns credential for valid token."""
    result = _credential_from_direct_token("sk-ant-oat01-abc", "test")
    assert result is not None
    assert result.access_token == "sk-ant-oat01-abc"
    assert result.source == "test"


# --- Lines 118-125: _iter_claude_code_credential_paths ---


def test_iter_claude_code_credential_paths_with_override(monkeypatch):
    """Lines 118-121: Includes override path when CLAUDE_CODE_CREDENTIALS_PATH is set."""
    monkeypatch.setenv("CLAUDE_CODE_CREDENTIALS_PATH", "/custom/path.json")
    paths = _iter_claude_code_credential_paths()
    assert Path("/custom/path.json") in paths
    assert any(".claude" in str(p) for p in paths)


def test_iter_claude_code_credential_paths_without_override(monkeypatch):
    """Lines 122-125: Only includes default path when no override."""
    monkeypatch.delenv("CLAUDE_CODE_CREDENTIALS_PATH", raising=False)
    paths = _iter_claude_code_credential_paths()
    assert len(paths) >= 1
    assert any(".claude" in str(p) for p in paths)


# --- Lines 132-133: _extract_claude_code_credential no access token ---


def test_extract_claude_code_credential_no_access_token():
    """Lines 132-133: Returns None when no accessToken."""
    data = {"claudeAiOauth": {}}
    assert _extract_claude_code_credential(data, "test") is None


def test_extract_claude_code_credential_empty_access_token():
    """Lines 132-133: Returns None when accessToken is empty."""
    data = {"claudeAiOauth": {"accessToken": ""}}
    assert _extract_claude_code_credential(data, "test") is None


# --- Lines 143-144: _extract_claude_code_credential expired ---


def test_extract_claude_code_credential_expired():
    """Lines 143-144: Returns None when token is expired."""
    data = {
        "claudeAiOauth": {
            "accessToken": "sk-ant-oat01-abc",
            "expiresAt": int(time.time() * 1000) - 120_000,
        }
    }
    assert _extract_claude_code_credential(data, "test") is None


def test_extract_claude_code_credential_valid():
    """Returns credential when token is valid."""
    data = {
        "claudeAiOauth": {
            "accessToken": "sk-ant-oat01-abc",
            "refreshToken": "sk-ant-ort01-abc",
            "expiresAt": int(time.time() * 1000) + 3600_000,
        }
    }
    cred = _extract_claude_code_credential(data, "test")
    assert cred is not None
    assert cred.access_token == "sk-ant-oat01-abc"
    assert cred.refresh_token == "sk-ant-ort01-abc"


# --- Lines 172-190: load_claude_code_credential branches ---


def test_load_claude_code_credential_from_fd(monkeypatch):
    """Lines 177-181: Loads from file descriptor."""
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"sk-ant-oat01-from-fd")
        os.close(write_fd)
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR", str(read_fd))
        # Ensure no direct token
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

        cred = load_claude_code_credential()
    finally:
        os.close(read_fd)

    assert cred is not None
    assert cred.access_token == "sk-ant-oat01-from-fd"
    assert cred.source == "claude-cli-fd"


def test_load_claude_code_credential_returns_none_when_nothing_found(tmp_path, monkeypatch):
    """Returns None when no credential source is available."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    cred = load_claude_code_credential()
    assert cred is None


# --- Lines 203, 206, 211-212: load_codex_cli_credential ---


def test_load_codex_cli_credential_returns_none_for_missing_file(tmp_path, monkeypatch):
    """Lines 203: Returns None when file doesn't exist."""
    monkeypatch.setenv("CODEX_AUTH_PATH", str(tmp_path / "missing.json"))
    assert load_codex_cli_credential() is None


def test_load_codex_cli_credential_returns_none_when_no_token(tmp_path, monkeypatch):
    """Lines 211-212: Returns None when no access token found."""
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"other_field": "value"}))
    monkeypatch.setenv("CODEX_AUTH_PATH", str(auth_path))
    assert load_codex_cli_credential() is None


def test_load_codex_cli_credential_with_legacy_token_field(tmp_path, monkeypatch):
    """Lines 206: Uses 'token' field as fallback."""
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"token": "legacy-token-value"}))
    monkeypatch.setenv("CODEX_AUTH_PATH", str(auth_path))

    cred = load_codex_cli_credential()
    assert cred is not None
    assert cred.access_token == "legacy-token-value"


def test_load_codex_cli_credential_with_non_dict_tokens(tmp_path, monkeypatch):
    """Line 203: Handles non-dict 'tokens' field."""
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"tokens": "not-a-dict", "access_token": "fallback-tok"}))
    monkeypatch.setenv("CODEX_AUTH_PATH", str(auth_path))

    cred = load_codex_cli_credential()
    assert cred is not None
    assert cred.access_token == "fallback-tok"


# --- _resolve_credential_path ---


def test_resolve_credential_path_with_env(monkeypatch, tmp_path):
    """Uses env var when set."""
    monkeypatch.setenv("TEST_CRED_PATH", str(tmp_path / "cred.json"))
    result = _resolve_credential_path("TEST_CRED_PATH", ".default/path")
    assert result == tmp_path / "cred.json"


def test_resolve_credential_path_default(monkeypatch):
    """Falls back to default relative path."""
    monkeypatch.delenv("TEST_CRED_PATH", raising=False)
    result = _resolve_credential_path("TEST_CRED_PATH", ".codex/auth.json")
    assert ".codex" in str(result)
