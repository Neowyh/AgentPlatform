"""Additional coverage tests for ideer.sandbox.local.local_sandbox_provider."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from ideer.sandbox.local import local_sandbox_provider as lsp_module
from ideer.sandbox.local.local_sandbox_provider import LocalSandboxProvider

# ===========================================================================
# acquire — thread caching and LRU eviction
# ===========================================================================


class TestLocalSandboxProviderAcquire:
    def test_acquire_generic_singleton(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                id1 = provider.acquire()
                id2 = provider.acquire()
                assert id1 == "local"
                assert id1 == id2
        finally:
            lsp_module._singleton = None

    def test_acquire_thread_scoped(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                with patch.object(provider, "_build_thread_path_mappings", return_value=[]):
                    id1 = provider.acquire("thread-1")
                    id2 = provider.acquire("thread-1")
                    assert id1 == "local:thread-1"
                    assert id1 == id2
        finally:
            lsp_module._singleton = None

    def test_acquire_different_threads(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                with patch.object(provider, "_build_thread_path_mappings", return_value=[]):
                    id1 = provider.acquire("thread-1")
                    id2 = provider.acquire("thread-2")
                    assert id1 != id2
        finally:
            lsp_module._singleton = None

    def test_lru_eviction(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider(max_cached_threads=2)
                with patch.object(provider, "_build_thread_path_mappings", return_value=[]):
                    provider.acquire("t1")
                    provider.acquire("t2")
                    provider.acquire("t3")  # should evict t1
                    # t1 should be evicted
                    assert "t1" not in provider._thread_sandboxes
                    assert "t2" in provider._thread_sandboxes
                    assert "t3" in provider._thread_sandboxes
        finally:
            lsp_module._singleton = None

    def test_move_to_end_on_hit(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider(max_cached_threads=2)
                with patch.object(provider, "_build_thread_path_mappings", return_value=[]):
                    provider.acquire("t1")
                    provider.acquire("t2")
                    provider.acquire("t1")  # promote t1
                    provider.acquire("t3")  # should evict t2, not t1
                    assert "t1" in provider._thread_sandboxes
                    assert "t2" not in provider._thread_sandboxes
        finally:
            lsp_module._singleton = None


# ===========================================================================
# get
# ===========================================================================


class TestLocalSandboxProviderGet:
    def test_get_generic(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                provider.acquire()
                sandbox = provider.get("local")
                assert sandbox is not None
        finally:
            lsp_module._singleton = None

    def test_get_thread(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                with patch.object(provider, "_build_thread_path_mappings", return_value=[]):
                    provider.acquire("t1")
                    sandbox = provider.get("local:t1")
                    assert sandbox is not None
        finally:
            lsp_module._singleton = None

    def test_get_unknown_id(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                result = provider.get("unknown-id")
                assert result is None
        finally:
            lsp_module._singleton = None

    def test_get_non_string(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                result = provider.get(123)
                assert result is None
        finally:
            lsp_module._singleton = None

    def test_get_generic_with_auto_acquire(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                # get("local") without prior acquire should auto-acquire
                sandbox = provider.get("local")
                assert sandbox is not None
        finally:
            lsp_module._singleton = None

    def test_get_thread_promotes_lru(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider(max_cached_threads=2)
                with patch.object(provider, "_build_thread_path_mappings", return_value=[]):
                    provider.acquire("t1")
                    provider.acquire("t2")
                    provider.get("local:t1")  # promote t1
                    provider.acquire("t3")  # should evict t2
                    assert "t1" in provider._thread_sandboxes
                    assert "t2" not in provider._thread_sandboxes
        finally:
            lsp_module._singleton = None


# ===========================================================================
# release / reset / shutdown
# ===========================================================================


class TestLocalSandboxProviderLifecycle:
    def test_release_is_noop(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                provider.acquire()
                provider.release("local")  # should not raise
        finally:
            lsp_module._singleton = None

    def test_reset_clears_all(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                with patch.object(provider, "_build_thread_path_mappings", return_value=[]):
                    provider.acquire("t1")
                    provider.reset()
                    assert lsp_module._singleton is None
                    assert len(provider._thread_sandboxes) == 0
        finally:
            lsp_module._singleton = None

    def test_shutdown_calls_reset(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                provider.acquire()
                provider.shutdown()
                assert lsp_module._singleton is None
        finally:
            lsp_module._singleton = None

    def test_reset_idempotent(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(mounts=None),
        )
        lsp_module._singleton = None
        try:
            with patch("ideer.config.get_app_config", return_value=config):
                provider = LocalSandboxProvider()
                provider.acquire()
                provider.reset()
                provider.reset()  # should not raise
        finally:
            lsp_module._singleton = None


# ===========================================================================
# _setup_path_mappings
# ===========================================================================


class TestSetupPathMappings:
    def test_config_exception(self):
        with patch("ideer.config.get_app_config", side_effect=Exception("fail")):
            provider = LocalSandboxProvider()
            assert provider._path_mappings == []

    def test_mount_host_path_does_not_exist(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills", get_skills_path=lambda: skills_dir),
            sandbox=SimpleNamespace(
                mounts=[
                    SimpleNamespace(host_path="/nonexistent/path", container_path="/mnt/data", read_only=False),
                ]
            ),
        )
        with patch("ideer.config.get_app_config", return_value=config):
            provider = LocalSandboxProvider()
            # Should not include mount with non-existent host path
            container_paths = [m.container_path for m in provider._path_mappings]
            assert "/mnt/data" not in container_paths
