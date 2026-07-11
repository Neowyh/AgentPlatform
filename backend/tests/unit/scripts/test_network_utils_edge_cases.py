"""Additional tests for packages.harness.ideer.utils.network — PortAllocator."""

from __future__ import annotations

import socket
import threading

import pytest

from packages.harness.ideer.utils.network import (
    PortAllocator,
    get_free_port,
    release_port,
)


class TestPortAllocator:
    def test_allocate_returns_available_port(self):
        allocator = PortAllocator()
        port = allocator.allocate(start_port=49152, max_range=10)
        assert isinstance(port, int)
        assert 49152 <= port < 49152 + 10

    def test_allocate_raises_when_no_port_available(self):
        allocator = PortAllocator()
        allocator._reserved_ports.update(range(50000, 50100))
        with pytest.raises(RuntimeError, match="No available port found"):
            allocator.allocate(start_port=50000, max_range=100)

    def test_allocate_reserves_port(self):
        allocator = PortAllocator()
        port = allocator.allocate(start_port=49152, max_range=10)
        assert port in allocator._reserved_ports

    def test_release_removes_port(self):
        allocator = PortAllocator()
        port = allocator.allocate(start_port=49152, max_range=10)
        allocator.release(port)
        assert port not in allocator._reserved_ports

    def test_release_nonexistent_port_is_noop(self):
        allocator = PortAllocator()
        allocator.release(99999)  # Should not raise

    def test_allocate_context_yields_port(self):
        allocator = PortAllocator()
        with allocator.allocate_context(start_port=49152, max_range=10) as port:
            assert isinstance(port, int)
            assert port in allocator._reserved_ports
        # After context exit, port should be released
        assert port not in allocator._reserved_ports

    def test_allocate_avoids_reserved_ports(self):
        allocator = PortAllocator()
        allocator._reserved_ports.add(49152)
        port = allocator.allocate(start_port=49152, max_range=10)
        assert port != 49152

    def test_allocate_skips_in_use_ports(self):
        """Allocate should skip ports that are actually bound."""
        allocator = PortAllocator()
        # Bind a port to ensure it's in use
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            bound_port = s.getsockname()[1]
            # Allocate from a range that includes the bound port
            start = max(49152, bound_port - 1)
            port = allocator.allocate(start_port=start, max_range=200)
            assert port != bound_port

    def test_thread_safety(self):
        """Multiple threads allocating should not get the same port."""
        allocator = PortAllocator()
        allocated_ports = []
        lock = threading.Lock()

        def worker():
            try:
                port = allocator.allocate(start_port=49152, max_range=500)
                with lock:
                    allocated_ports.append(port)
            except RuntimeError:
                pass

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # All allocated ports should be unique
        assert len(allocated_ports) == len(set(allocated_ports))

    def test_max_range_boundary(self):
        """Allocate with max_range=1 should try exactly one port."""
        allocator = PortAllocator()
        # Find a port that's actually available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            available = s.getsockname()[1]
        port = allocator.allocate(start_port=available, max_range=1)
        assert port == available

    def test_max_range_boundary_fail(self):
        """Allocate with max_range=1 when port is reserved should fail."""
        allocator = PortAllocator()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            available = s.getsockname()[1]
        allocator._reserved_ports.add(available)
        with pytest.raises(RuntimeError, match="No available port found"):
            allocator.allocate(start_port=available, max_range=1)


class TestGlobalPortAllocator:
    def test_get_free_port_returns_int(self):
        port = get_free_port(start_port=49152, max_range=10)
        assert isinstance(port, int)
        release_port(port)

    def test_release_port_does_not_raise(self):
        port = get_free_port(start_port=49152, max_range=10)
        release_port(port)  # Should not raise
