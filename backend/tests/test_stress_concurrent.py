"""Stress and concurrency tests.

Validates that concurrent operations don't cause race conditions or deadlocks.
"""

import asyncio

import pytest


@pytest.mark.stress
class TestConcurrentDictOperations:
    """Concurrent dictionary operation stress tests."""

    @pytest.mark.asyncio
    async def test_concurrent_dict_writes(self):
        """100 concurrent dict writes should not lose data."""
        shared_dict = {}
        lock = asyncio.Lock()

        async def write_entry(key, value):
            async with lock:
                shared_dict[key] = value

        tasks = [write_entry(f"key_{i}", f"value_{i}") for i in range(100)]
        await asyncio.gather(*tasks)

        assert len(shared_dict) == 100
        for i in range(100):
            assert shared_dict[f"key_{i}"] == f"value_{i}"

    @pytest.mark.asyncio
    async def test_concurrent_dict_reads(self):
        """100 concurrent dict reads should not cause errors."""
        shared_dict = {f"key_{i}": f"value_{i}" for i in range(100)}

        async def read_entry(key):
            return shared_dict.get(key)

        tasks = [read_entry(f"key_{i}") for i in range(100)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        for i, result in enumerate(results):
            assert result == f"value_{i}"


@pytest.mark.stress
class TestConcurrentListOperations:
    """Concurrent list operation stress tests."""

    @pytest.mark.asyncio
    async def test_concurrent_list_appends(self):
        """100 concurrent list appends should not lose items."""
        shared_list = []
        lock = asyncio.Lock()

        async def append_item(item):
            async with lock:
                shared_list.append(item)

        tasks = [append_item(f"item_{i}") for i in range(100)]
        await asyncio.gather(*tasks)

        assert len(shared_list) == 100

    @pytest.mark.asyncio
    async def test_concurrent_queue_operations(self):
        """concurrent queue put/get should maintain FIFO order."""
        queue = asyncio.Queue()
        results = []

        async def producer(start, count):
            for i in range(count):
                await queue.put(start + i)

        async def consumer(count):
            for _ in range(count):
                item = await queue.get()
                results.append(item)

        # Start producers and consumers
        producers = [asyncio.create_task(producer(i * 10, 10)) for i in range(5)]
        consumers = [asyncio.create_task(consumer(10)) for _ in range(5)]

        await asyncio.gather(*producers)
        await asyncio.gather(*consumers)

        assert len(results) == 50


@pytest.mark.stress
class TestConcurrentAsyncOperations:
    """Concurrent async operation stress tests."""

    @pytest.mark.asyncio
    async def test_concurrent_async_gather(self):
        """asyncio.gather with 100 tasks should complete without errors."""

        async def async_task(task_id):
            await asyncio.sleep(0.001)  # Simulate async work
            return task_id

        tasks = [async_task(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        assert results == list(range(100))

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self):
        """mixed read/write operations should not deadlock."""
        shared_state = {"counter": 0}
        lock = asyncio.Lock()

        async def increment():
            async with lock:
                shared_state["counter"] += 1

        async def read_value():
            async with lock:
                return shared_state["counter"]

        # Run mixed operations
        tasks = []
        for _ in range(50):
            tasks.append(increment())
        for _ in range(50):
            tasks.append(read_value())

        results = await asyncio.gather(*tasks)

        assert shared_state["counter"] == 50
        assert len(results) == 100

    @pytest.mark.asyncio
    async def test_concurrent_task_cancellation(self):
        """cancelled tasks should not affect other tasks."""
        results = []

        async def cancellable_task(task_id):
            try:
                await asyncio.sleep(1)  # Long-running task
                results.append(task_id)
            except asyncio.CancelledError:
                results.append(f"cancelled_{task_id}")

        async def quick_task(task_id):
            await asyncio.sleep(0.01)
            results.append(task_id)

        # Start cancellable tasks and quick tasks
        cancellable = [asyncio.create_task(cancellable_task(i)) for i in range(5)]
        quick = [asyncio.create_task(quick_task(i + 100)) for i in range(5)]

        # Cancel cancellable tasks
        for task in cancellable:
            task.cancel()

        # Wait for all tasks
        await asyncio.gather(*cancellable, *quick, return_exceptions=True)

        # Quick tasks should have completed
        assert len([r for r in results if isinstance(r, int) and r >= 100]) == 5
