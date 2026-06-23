"""Additional tests for ideer.utils.network — coverage gaps.

Covers:
  - Lines 55-56: _is_port_available actual socket bind (0.0.0.0)
"""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from ideer.utils.network import PortAllocator, get_free_port, release_port

# ---------------------------------------------------------------------------
# Lines 55-56: _is_port_available socket bind on 0.0.0.0
# ---------------------------------------------------------------------------


class TestIsPortAvailable:
    def test_port_available_returns_true(self):
        """Available port should return True."""
        allocator = PortAllocator()
        # Find a port that's actually free
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            free_port = s.getsockname()[1]
        # Release the socket so the port becomes available
        # Now test _is_port_available
        assert allocator._is_port_available(free_port) is True

    def test_port_in_reserved_set_returns_false(self):
        """Port in reserved set should return False without socket check."""
        allocator = PortAllocator()
        allocator._reserved_ports.add(12345)
        assert allocator._is_port_available(12345) is False

    def test_port_bound_by_another_process_returns_false(self):
        """Port actually bound by another socket should return False."""
        allocator = PortAllocator()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            bound_port = s.getsockname()[1]
            # Port is still bound, so should be unavailable
            assert allocator._is_port_available(bound_port) is False

    def test_bind_oserror_returns_false(self):
        """When socket.bind raises OSError, port is unavailable."""
        allocator = PortAllocator()
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock.__exit__ = MagicMock(return_value=False)
            mock_sock.bind.side_effect = OSError("Address already in use")
            mock_sock_cls.return_value = mock_sock
            assert allocator._is_port_available(8080) is False

    def test_allocate_finds_available_port(self):
        """allocate() should find and reserve an available port."""
        allocator = PortAllocator()
        port = allocator.allocate(start_port=49152, max_range=100)
        assert isinstance(port, int)
        assert port in allocator._reserved_ports
        allocator.release(port)

    def test_allocate_with_all_ports_reserved(self):
        """When all ports in range are reserved, allocate raises."""
        allocator = PortAllocator()
        for p in range(50000, 50100):
            allocator._reserved_ports.add(p)
        with pytest.raises(RuntimeError, match="No available port found"):
            allocator.allocate(start_port=50000, max_range=100)

    def test_context_manager_releases_on_exit(self):
        """allocate_context should release port on context exit."""
        allocator = PortAllocator()
        with allocator.allocate_context(start_port=49152, max_range=100) as port:
            assert port in allocator._reserved_ports
        assert port not in allocator._reserved_ports

    def test_context_manager_releases_on_exception(self):
        """allocate_context should release port even when exception occurs."""
        allocator = PortAllocator()
        with pytest.raises(ValueError):
            with allocator.allocate_context(start_port=49152, max_range=100) as port:
                assert port in allocator._reserved_ports
                raise ValueError("test error")
        assert port not in allocator._reserved_ports

    def test_global_get_free_port_and_release(self):
        """Global get_free_port and release_port should work together."""
        port = get_free_port(start_port=49152, max_range=100)
        assert isinstance(port, int)
        release_port(port)

    def test_thread_safety_multiple_allocators(self):
        """Multiple threads using the same allocator get different ports."""
        import threading

        allocator = PortAllocator()
        ports = []
        lock = threading.Lock()

        def worker():
            try:
                p = allocator.allocate(start_port=49200, max_range=500)
                with lock:
                    ports.append(p)
            except RuntimeError:
                pass

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(ports) == len(set(ports)), "All ports should be unique"
