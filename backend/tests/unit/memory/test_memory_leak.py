"""Memory leak detection tests.

Validates that repeated operations don't cause memory leaks.
"""

import tracemalloc
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest


class TestMemoryLeakDetection:
    """Memory leak detection tests using tracemalloc."""

    def test_no_leak_in_object_creation_destruction(self):
        """repeated object creation/destruction should not leak memory."""
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        # Create and destroy many objects
        for _ in range(1000):
            obj = SimpleNamespace(
                id=str(uuid4()),
                name="test",
                data="x" * 100,
            )
            del obj

        snapshot2 = tracemalloc.take_snapshot()
        top_stats = snapshot2.compare_to(snapshot1, "lineno")

        # Check for significant memory growth (more than 1MB)
        for stat in top_stats[:5]:
            assert stat.size_diff < 1024 * 1024, f"Potential memory leak: {stat}"

        tracemalloc.stop()

    def test_no_leak_in_dict_operations(self):
        """repeated dict operations should not leak memory."""
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        for _ in range(1000):
            d = {}
            for i in range(100):
                d[f"key_{i}"] = f"value_{i}"
            d.clear()
            del d

        snapshot2 = tracemalloc.take_snapshot()
        top_stats = snapshot2.compare_to(snapshot1, "lineno")

        for stat in top_stats[:5]:
            assert stat.size_diff < 1024 * 1024, f"Potential memory leak: {stat}"

        tracemalloc.stop()

    def test_no_leak_in_list_operations(self):
        """repeated list operations should not leak memory."""
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        for _ in range(1000):
            lst = []
            for i in range(100):
                lst.append(f"item_{i}")
            lst.clear()
            del lst

        snapshot2 = tracemalloc.take_snapshot()
        top_stats = snapshot2.compare_to(snapshot1, "lineno")

        for stat in top_stats[:5]:
            assert stat.size_diff < 1024 * 1024, f"Potential memory leak: {stat}"

        tracemalloc.stop()

    def test_no_leak_in_mock_creation(self):
        """repeated mock creation should not leak memory."""
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        for _ in range(1000):
            mock = MagicMock()
            mock.method.return_value = "value"
            mock.data = {"key": "value"}
            del mock

        snapshot2 = tracemalloc.take_snapshot()
        top_stats = snapshot2.compare_to(snapshot1, "lineno")

        for stat in top_stats[:5]:
            assert stat.size_diff < 1024 * 1024, f"Potential memory leak: {stat}"

        tracemalloc.stop()


class TestResourceCleanup:
    """Resource cleanup tests."""

    def test_context_manager_cleanup(self):
        """context managers should properly clean up resources."""
        resources = []

        class ManagedResource:
            def __enter__(self):
                resources.append(self)
                return self

            def __exit__(self, *args):
                resources.remove(self)

        # Use and cleanup many resources
        for _ in range(100):
            with ManagedResource():
                pass

        assert len(resources) == 0

    def test_exception_cleanup(self):
        """resources should be cleaned up even on exceptions."""
        resources = []

        class ManagedResource:
            def __enter__(self):
                resources.append(self)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                resources.remove(self)
                return False  # Don't suppress exceptions

        for _ in range(100):
            try:
                with ManagedResource():
                    raise ValueError("test error")
            except ValueError:
                pass

        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_async_cleanup(self):
        """async resources should be properly cleaned up."""
        cleanup_count = 0

        class AsyncResource:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                nonlocal cleanup_count
                cleanup_count += 1

        for _ in range(100):
            async with AsyncResource():
                pass

        assert cleanup_count == 100
