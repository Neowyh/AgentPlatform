"""Tests for ideer.community.aio_sandbox.local_backend — LocalContainerBackend."""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ideer.community.aio_sandbox.local_backend import (
    LocalContainerBackend,
    _extract_host_port,
    _format_container_command_for_log,
    _format_container_mount,
    _is_ipv6_loopback_sandbox_host,
    _is_loopback_sandbox_host,
    _normalize_sandbox_host,
    _parse_docker_timestamp,
    _redact_container_command_for_log,
    _resolve_docker_bind_host,
)

# ---------------------------------------------------------------------------
# _parse_docker_timestamp
# ---------------------------------------------------------------------------


class TestParseDockerTimestamp:
    def test_empty(self):
        assert _parse_docker_timestamp("") == 0.0

    def test_full_timestamp(self):
        result = _parse_docker_timestamp("2026-04-08T01:22:50.123456789Z")
        assert result > 0

    def test_no_fractional(self):
        result = _parse_docker_timestamp("2026-04-08T01:22:50Z")
        assert result > 0

    def test_with_offset(self):
        result = _parse_docker_timestamp("2026-04-08T01:22:50+00:00")
        assert result > 0

    def test_invalid(self):
        assert _parse_docker_timestamp("not-a-date") == 0.0

    def test_none(self):
        assert _parse_docker_timestamp(None) == 0.0

    def test_microsecond_precision(self):
        result = _parse_docker_timestamp("2026-04-08T01:22:50.123456Z")
        assert result > 0


# ---------------------------------------------------------------------------
# _extract_host_port
# ---------------------------------------------------------------------------


class TestExtractHostPort:
    def test_with_port(self):
        entry = {
            "NetworkSettings": {
                "Ports": {
                    "8080/tcp": [{"HostPort": "12345"}],
                },
            },
        }
        assert _extract_host_port(entry, 8080) == 12345

    def test_no_port(self):
        entry = {"NetworkSettings": {"Ports": {}}}
        assert _extract_host_port(entry, 8080) is None

    def test_empty_bindings(self):
        entry = {
            "NetworkSettings": {
                "Ports": {"8080/tcp": []},
            },
        }
        assert _extract_host_port(entry, 8080) is None

    def test_no_network_settings(self):
        assert _extract_host_port({}, 8080) is None

    def test_invalid_port_value(self):
        entry = {
            "NetworkSettings": {
                "Ports": {
                    "8080/tcp": [{"HostPort": "not_a_number"}],
                },
            },
        }
        assert _extract_host_port(entry, 8080) is None


# ---------------------------------------------------------------------------
# _format_container_mount
# ---------------------------------------------------------------------------


class TestFormatContainerMount:
    def test_docker_mount(self):
        result = _format_container_mount("docker", "/host", "/container", False)
        assert result[0] == "--mount"
        assert "type=bind" in result[1]
        assert "/host" in result[1]
        assert "/container" in result[1]
        assert "readonly" not in result[1]

    def test_docker_readonly(self):
        result = _format_container_mount("docker", "/host", "/container", True)
        assert "readonly" in result[1]

    def test_container_mount(self):
        result = _format_container_mount("container", "/host", "/container", False)
        assert result[0] == "-v"
        assert "/host:/container" == result[1]

    def test_container_readonly(self):
        result = _format_container_mount("container", "/host", "/container", True)
        assert result[1] == "/host:/container:ro"


# ---------------------------------------------------------------------------
# _redact_container_command_for_log
# ---------------------------------------------------------------------------


class TestRedactContainerCommandForLog:
    def test_redacts_env_flag(self):
        cmd = ["docker", "run", "-e", "SECRET_KEY=mysecret", "-e", "DB_PASS=pass123"]
        result = _redact_container_command_for_log(cmd)
        assert "SECRET_KEY=<redacted>" in result
        assert "DB_PASS=<redacted>" in result
        assert "mysecret" not in str(result)
        assert "pass123" not in str(result)

    def test_redacts_env_equals(self):
        cmd = ["docker", "run", "--env=MY_VAR=value"]
        result = _redact_container_command_for_log(cmd)
        assert "--env=MY_VAR=<redacted>" in result

    def test_no_env(self):
        cmd = ["docker", "run", "-d", "--name", "test"]
        result = _redact_container_command_for_log(cmd)
        assert result == cmd

    def test_env_flag_without_value(self):
        cmd = ["docker", "run", "-e", "NEXT_ARG"]
        result = _redact_container_command_for_log(cmd)
        # NEXT_ARG doesn't have =, so it's kept as-is
        assert "NEXT_ARG" in result


# ---------------------------------------------------------------------------
# _format_container_command_for_log
# ---------------------------------------------------------------------------


class TestFormatContainerCommandForLog:
    def test_format(self):
        cmd = ["docker", "run", "-e", "KEY=VAL"]
        result = _format_container_command_for_log(cmd)
        assert "docker" in result
        assert "run" in result


# ---------------------------------------------------------------------------
# _normalize_sandbox_host
# ---------------------------------------------------------------------------


class TestNormalizeSandboxHost:
    def test_strips_whitespace(self):
        assert _normalize_sandbox_host("  localhost  ") == "localhost"

    def test_lowercase(self):
        assert _normalize_sandbox_host("LOCALHOST") == "localhost"


# ---------------------------------------------------------------------------
# _is_ipv6_loopback_sandbox_host
# ---------------------------------------------------------------------------


class TestIsIpv6Loopback:
    def test_colon_one(self):
        assert _is_ipv6_loopback_sandbox_host("::1") is True

    def test_bracketed(self):
        assert _is_ipv6_loopback_sandbox_host("[::1]") is True

    def test_not_ipv6(self):
        assert _is_ipv6_loopback_sandbox_host("127.0.0.1") is False


# ---------------------------------------------------------------------------
# _is_loopback_sandbox_host
# ---------------------------------------------------------------------------


class TestIsLoopbackSandboxHost:
    def test_localhost(self):
        assert _is_loopback_sandbox_host("localhost") is True

    def test_127(self):
        assert _is_loopback_sandbox_host("127.0.0.1") is True

    def test_empty(self):
        assert _is_loopback_sandbox_host("") is True

    def test_ipv6(self):
        assert _is_loopback_sandbox_host("::1") is True

    def test_external(self):
        assert _is_loopback_sandbox_host("192.168.1.1") is False


# ---------------------------------------------------------------------------
# _resolve_docker_bind_host
# ---------------------------------------------------------------------------


class TestResolveDockerBindHost:
    def test_explicit_bind(self):
        result = _resolve_docker_bind_host(bind_host="0.0.0.0")
        assert result == "0.0.0.0"

    def test_ipv6_loopback(self):
        result = _resolve_docker_bind_host(sandbox_host="::1")
        assert result == "[::1]"

    def test_loopback_default(self):
        result = _resolve_docker_bind_host(sandbox_host="localhost")
        assert result == "127.0.0.1"

    def test_non_loopback(self):
        result = _resolve_docker_bind_host(sandbox_host="host.docker.internal")
        assert result == "0.0.0.0"

    def test_default_no_args(self):
        with patch.dict("os.environ", {}, clear=True):
            result = _resolve_docker_bind_host()
            assert result == "127.0.0.1"

    def test_env_override(self):
        with patch.dict("os.environ", {"IDEER_SANDBOX_BIND_HOST": "10.0.0.1"}):
            result = _resolve_docker_bind_host()
            assert result == "10.0.0.1"

    def test_env_override_empty_string(self):
        with patch.dict("os.environ", {"IDEER_SANDBOX_BIND_HOST": ""}):
            result = _resolve_docker_bind_host(sandbox_host="localhost")
            assert result == "127.0.0.1"


# ---------------------------------------------------------------------------
# LocalContainerBackend construction
# ---------------------------------------------------------------------------


class TestLocalContainerBackendInit:
    def test_defaults(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test-image:latest",
                base_port=8080,
                container_prefix="ideer-sandbox",
                config_mounts=[],
                environment={},
            )
            assert backend._image == "test-image:latest"
            assert backend._base_port == 8080
            assert backend.runtime == "docker"


# ---------------------------------------------------------------------------
# _detect_runtime
# ---------------------------------------------------------------------------


class TestDetectRuntime:
    def test_linux_uses_docker(self):
        with patch("platform.system", return_value="Linux"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )
            assert backend.runtime == "docker"

    def test_darwin_with_container(self):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", return_value=MagicMock(stdout="container version 1.0")):
                backend = LocalContainerBackend(
                    image="test",
                    base_port=8080,
                    container_prefix="ideer",
                    config_mounts=[],
                    environment={},
                )
                assert backend.runtime == "container"

    def test_darwin_without_container(self):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                backend = LocalContainerBackend(
                    image="test",
                    base_port=8080,
                    container_prefix="ideer",
                    config_mounts=[],
                    environment={},
                )
                assert backend.runtime == "docker"


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestCreate:
    def test_create_success(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test-image:latest",
                base_port=8080,
                container_prefix="ideer-sandbox",
                config_mounts=[],
                environment={"ENV": "test"},
            )

        with patch("ideer.community.aio_sandbox.local_backend.get_free_port", return_value=12345):
            with patch.object(backend, "_start_container", return_value="container_id_123"):
                with patch.dict("os.environ", {"IDEER_SANDBOX_HOST": "localhost"}):
                    info = backend.create("thread_1", "sandbox_1")
                    assert info.sandbox_id == "sandbox_1"
                    assert ":12345" in info.sandbox_url
                    assert info.container_id == "container_id_123"

    def test_create_port_retry(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test-image:latest",
                base_port=8080,
                container_prefix="ideer-sandbox",
                config_mounts=[],
                environment={},
            )

        call_count = 0

        def mock_start(name, port, extra=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("port is already allocated")
            return "container_id"

        with patch("ideer.community.aio_sandbox.local_backend.get_free_port", side_effect=[10001, 10002]):
            with patch("ideer.community.aio_sandbox.local_backend.release_port"):
                with patch.object(backend, "_start_container", side_effect=mock_start):
                    with patch.dict("os.environ", {"IDEER_SANDBOX_HOST": "localhost"}):
                        info = backend.create("thread_1", "sandbox_1")
                        assert info.container_id == "container_id"

    def test_create_all_ports_allocated(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test-image:latest",
                base_port=8080,
                container_prefix="ideer-sandbox",
                config_mounts=[],
                environment={},
            )

        with patch("ideer.community.aio_sandbox.local_backend.get_free_port", return_value=10001):
            with patch("ideer.community.aio_sandbox.local_backend.release_port"):
                with patch.object(backend, "_start_container", side_effect=RuntimeError("port is already allocated")):
                    with pytest.raises(RuntimeError, match="all candidate ports"):
                        backend.create("thread_1", "sandbox_1")

    def test_create_name_conflict_discover(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test-image:latest",
                base_port=8080,
                container_prefix="ideer-sandbox",
                config_mounts=[],
                environment={},
            )

        existing_info = SimpleNamespace(
            sandbox_id="sandbox_1",
            sandbox_url="http://localhost:9999",
            container_name="ideer-sandbox-sandbox_1",
        )

        with patch("ideer.community.aio_sandbox.local_backend.get_free_port", return_value=10001):
            with patch("ideer.community.aio_sandbox.local_backend.release_port"):
                with patch.object(backend, "_start_container", side_effect=RuntimeError("is already in use by container")):
                    with patch.object(backend, "discover", return_value=existing_info):
                        info = backend.create("thread_1", "sandbox_1")
                        assert info is existing_info


# ---------------------------------------------------------------------------
# destroy()
# ---------------------------------------------------------------------------


class TestDestroy:
    def test_destroy_with_container_id(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        info = SimpleNamespace(
            sandbox_id="s1",
            sandbox_url="http://localhost:12345",
            container_name="ideer-s1",
            container_id="cid_123",
        )

        with patch.object(backend, "_stop_container") as mock_stop:
            with patch("ideer.community.aio_sandbox.local_backend.release_port"):
                backend.destroy(info)
                mock_stop.assert_called_once_with("cid_123")

    def test_destroy_with_name_only(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        info = SimpleNamespace(
            sandbox_id="s1",
            sandbox_url="http://localhost:12345",
            container_name="ideer-s1",
            container_id=None,
        )

        with patch.object(backend, "_stop_container") as mock_stop:
            with patch("ideer.community.aio_sandbox.local_backend.release_port"):
                backend.destroy(info)
                mock_stop.assert_called_once_with("ideer-s1")


# ---------------------------------------------------------------------------
# is_alive()
# ---------------------------------------------------------------------------


class TestIsAlive:
    def test_alive(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        info = SimpleNamespace(container_name="ideer-s1")
        with patch.object(backend, "_is_container_running", return_value=True):
            assert backend.is_alive(info) is True

    def test_dead(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        info = SimpleNamespace(container_name="ideer-s1")
        with patch.object(backend, "_is_container_running", return_value=False):
            assert backend.is_alive(info) is False

    def test_no_name(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        info = SimpleNamespace(container_name=None)
        assert backend.is_alive(info) is False


# ---------------------------------------------------------------------------
# discover()
# ---------------------------------------------------------------------------


class TestDiscover:
    def test_discover_not_running(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch.object(backend, "_is_container_running", return_value=False):
            assert backend.discover("sandbox_1") is None

    def test_discover_no_port(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch.object(backend, "_is_container_running", return_value=True):
            with patch.object(backend, "_get_container_port", return_value=None):
                assert backend.discover("sandbox_1") is None

    def test_discover_not_ready(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch.object(backend, "_is_container_running", return_value=True):
            with patch.object(backend, "_get_container_port", return_value=12345):
                with patch("ideer.community.aio_sandbox.local_backend.wait_for_sandbox_ready", return_value=False):
                    assert backend.discover("sandbox_1") is None

    def test_discover_success(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch.object(backend, "_is_container_running", return_value=True):
            with patch.object(backend, "_get_container_port", return_value=12345):
                with patch("ideer.community.aio_sandbox.local_backend.wait_for_sandbox_ready", return_value=True):
                    with patch.dict("os.environ", {"IDEER_SANDBOX_HOST": "localhost"}):
                        info = backend.discover("sandbox_1")
                        assert info is not None
                        assert info.sandbox_id == "sandbox_1"
                        assert ":12345" in info.sandbox_url


# ---------------------------------------------------------------------------
# list_running()
# ---------------------------------------------------------------------------


class TestListRunning:
    def test_empty(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = backend.list_running()
            assert result == []

    def test_with_containers(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        ps_result = MagicMock()
        ps_result.returncode = 0
        ps_result.stdout = "ideer-sandbox-abc\ndef\n"

        inspect_data = [
            {
                "Name": "/ideer-sandbox-abc",
                "Created": "2026-04-08T01:22:50Z",
                "NetworkSettings": {
                    "Ports": {"8080/tcp": [{"HostPort": "12345"}]},
                },
            },
        ]

        def mock_subprocess_run(cmd, **kwargs):
            if "ps" in cmd:
                return ps_result
            if "inspect" in cmd:
                inspect_result = MagicMock()
                inspect_result.returncode = 0
                inspect_result.stdout = json.dumps(inspect_data)
                return inspect_result
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            with patch.dict("os.environ", {"IDEER_SANDBOX_HOST": "localhost"}):
                result = backend.list_running()
                assert len(result) == 1
                assert result[0].sandbox_id == "sandbox-abc"

    def test_ps_failure(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("subprocess.run", return_value=mock_result):
            result = backend.list_running()
            assert result == []

    def test_ps_exception(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch("subprocess.run", side_effect=OSError("docker not found")):
            result = backend.list_running()
            assert result == []


# ---------------------------------------------------------------------------
# _batch_inspect
# ---------------------------------------------------------------------------


class TestBatchInspect:
    def test_empty(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        assert backend._batch_inspect([]) == {}

    def test_success(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        inspect_data = [
            {
                "Name": "/container-1",
                "Created": "2026-04-08T01:22:50Z",
                "NetworkSettings": {
                    "Ports": {"8080/tcp": [{"HostPort": "12345"}]},
                },
            },
        ]

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(inspect_data)

        with patch("subprocess.run", return_value=mock_result):
            result = backend._batch_inspect(["container-1"])
            assert "container-1" in result
            assert result["container-1"][1] == 12345

    def test_failure(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("subprocess.run", return_value=mock_result):
            result = backend._batch_inspect(["container-1"])
            assert result == {}

    def test_invalid_json(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"

        with patch("subprocess.run", return_value=mock_result):
            result = backend._batch_inspect(["container-1"])
            assert result == {}

    def test_exception(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch("subprocess.run", side_effect=OSError("fail")):
            result = backend._batch_inspect(["container-1"])
            assert result == {}


# ---------------------------------------------------------------------------
# _start_container
# ---------------------------------------------------------------------------


class TestStartContainer:
    def test_success(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test-image:latest",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={"ENV": "test"},
            )

        mock_result = MagicMock()
        mock_result.stdout = "container_id_abc"

        with patch("subprocess.run", return_value=mock_result):
            with patch.dict("os.environ", {"IDEER_SANDBOX_BIND_HOST": "127.0.0.1"}):
                cid = backend._start_container("ideer-test", 12345)
                assert cid == "container_id_abc"

    def test_failure(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test-image:latest",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "docker", stderr="fail")):
            with pytest.raises(RuntimeError, match="Failed to start"):
                backend._start_container("ideer-test", 12345)

    def test_with_extra_mounts(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test-image:latest",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.stdout = "cid"

        with patch("subprocess.run", return_value=mock_result):
            with patch.dict("os.environ", {"IDEER_SANDBOX_BIND_HOST": "127.0.0.1"}):
                cid = backend._start_container("ideer-test", 12345, extra_mounts=[("/host", "/container", False)])
                assert cid == "cid"


# ---------------------------------------------------------------------------
# _stop_container
# ---------------------------------------------------------------------------


class TestStopContainer:
    def test_success(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch("subprocess.run", return_value=MagicMock()):
            backend._stop_container("cid_123")

    def test_failure(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "docker", stderr="fail")):
            # Should not raise
            backend._stop_container("cid_123")


# ---------------------------------------------------------------------------
# _is_container_running
# ---------------------------------------------------------------------------


class TestIsContainerRunning:
    def test_running(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "true"

        with patch("subprocess.run", return_value=mock_result):
            assert backend._is_container_running("container-1") is True

    def test_not_running(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "false"

        with patch("subprocess.run", return_value=mock_result):
            assert backend._is_container_running("container-1") is False

    def test_inspect_error(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "docker")):
            assert backend._is_container_running("container-1") is False


# ---------------------------------------------------------------------------
# _get_container_port
# ---------------------------------------------------------------------------


class TestGetContainerPort:
    def test_with_port(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0.0.0.0:12345"

        with patch("subprocess.run", return_value=mock_result):
            assert backend._get_container_port("container-1") == 12345

    def test_no_port(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            assert backend._get_container_port("container-1") is None

    def test_ipv6_format(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ":::12345"

        with patch("subprocess.run", return_value=mock_result):
            assert backend._get_container_port("container-1") == 12345

    def test_timeout(self):
        with patch.object(LocalContainerBackend, "_detect_runtime", return_value="docker"):
            backend = LocalContainerBackend(
                image="test",
                base_port=8080,
                container_prefix="ideer",
                config_mounts=[],
                environment={},
            )

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 5)):
            assert backend._get_container_port("container-1") is None
