"""Tests for ideer.sandbox.file_operation_lock — file operation lock utilities."""

from __future__ import annotations

import threading
import weakref
from unittest.mock import MagicMock

from ideer.sandbox.file_operation_lock import (
    _FILE_OPERATION_LOCKS,
    get_file_operation_lock,
    get_file_operation_lock_key,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sandbox(sandbox_id: str = "sb-1") -> MagicMock:
    sb = MagicMock()
    sb.id = sandbox_id
    return sb


def _make_sandbox_no_id() -> MagicMock:
    sb = MagicMock(spec=[])  # no attributes
    return sb


# ---------------------------------------------------------------------------
# get_file_operation_lock_key
# ---------------------------------------------------------------------------


class TestGetFileOperationLockKey:
    def test_key_with_sandbox_id(self):
        sb = _make_sandbox("sb-42")
        key = get_file_operation_lock_key(sb, "/tmp/file.txt")
        assert key == ("sb-42", "/tmp/file.txt")

    def test_key_without_sandbox_id_falls_back_to_instance_id(self):
        sb = _make_sandbox_no_id()
        key = get_file_operation_lock_key(sb, "/tmp/file.txt")
        assert key == (f"instance:{id(sb)}", "/tmp/file.txt")

    def test_key_with_empty_id_falls_back(self):
        sb = _make_sandbox("")
        key = get_file_operation_lock_key(sb, "/tmp/file.txt")
        assert key == (f"instance:{id(sb)}", "/tmp/file.txt")


# ---------------------------------------------------------------------------
# get_file_operation_lock — basic behaviour
# ---------------------------------------------------------------------------


class TestGetFileOperationLock:
    def test_returns_lock_instance(self):
        sb = _make_sandbox()
        lock = get_file_operation_lock(sb, "/a.txt")
        assert isinstance(lock, type(threading.Lock()))

    def test_same_path_returns_same_lock(self):
        sb = _make_sandbox()
        lock1 = get_file_operation_lock(sb, "/a.txt")
        lock2 = get_file_operation_lock(sb, "/a.txt")
        assert lock1 is lock2

    def test_different_paths_return_different_locks(self):
        sb = _make_sandbox()
        lock_a = get_file_operation_lock(sb, "/a.txt")
        lock_b = get_file_operation_lock(sb, "/b.txt")
        assert lock_a is not lock_b

    def test_different_sandboxes_different_ids_different_locks(self):
        sb1 = _make_sandbox("sb-1")
        sb2 = _make_sandbox("sb-2")
        lock1 = get_file_operation_lock(sb1, "/a.txt")
        lock2 = get_file_operation_lock(sb2, "/a.txt")
        assert lock1 is not lock2

    def test_same_path_different_sandboxes_different_locks(self):
        sb1 = _make_sandbox("sb-1")
        sb2 = _make_sandbox("sb-2")
        lock1 = get_file_operation_lock(sb1, "/shared.txt")
        lock2 = get_file_operation_lock(sb2, "/shared.txt")
        assert lock1 is not lock2


# ---------------------------------------------------------------------------
# Lock acquisition and release
# ---------------------------------------------------------------------------


class TestLockAcquireRelease:
    def test_acquire_and_release(self):
        sb = _make_sandbox()
        lock = get_file_operation_lock(sb, "/a.txt")
        assert lock.acquire(blocking=False) is True
        assert lock.locked() is True
        lock.release()
        assert lock.locked() is False

    def test_release_then_reacquire(self):
        sb = _make_sandbox()
        lock = get_file_operation_lock(sb, "/a.txt")
        lock.acquire()
        lock.release()
        assert lock.acquire(timeout=1) is True
        lock.release()

    def test_timeout_when_already_held(self):
        """A second acquire on a non-reentrant lock should time out."""
        sb = _make_sandbox()
        lock = get_file_operation_lock(sb, "/a.txt")
        lock.acquire(blocking=False)
        # Same thread trying to acquire again — non-reentrant, should timeout
        assert lock.acquire(timeout=0.05) is False
        lock.release()


# ---------------------------------------------------------------------------
# Thread safety — concurrent acquisition
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_only_one_thread_holds_lock(self):
        """Verify mutual exclusion: no two threads are in the critical section simultaneously."""
        import time

        sb = _make_sandbox()
        lock = get_file_operation_lock(sb, "/shared.txt")
        concurrent_holders = 0
        max_concurrent = 0
        counter_lock = threading.Lock()
        started = threading.Event()
        stop = threading.Event()

        def worker():
            nonlocal concurrent_holders, max_concurrent
            lock.acquire()
            with counter_lock:
                concurrent_holders += 1
                if concurrent_holders > max_concurrent:
                    max_concurrent = concurrent_holders
            started.set()
            # Hold the lock long enough for other threads to attempt acquisition
            stop.wait(timeout=2)
            with counter_lock:
                concurrent_holders -= 1
            lock.release()

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        # Wait until at least one thread holds the lock
        started.wait(timeout=2)
        # Give other threads time to try (and fail) to acquire
        time.sleep(0.05)
        stop.set()
        for t in threads:
            t.join(timeout=5)

        assert max_concurrent == 1, f"Expected at most 1 concurrent holder, got {max_concurrent}"

    def test_different_paths_no_contention(self):
        """Threads operating on different paths should not block each other."""
        sb = _make_sandbox()
        barrier = threading.Barrier(2)
        results = {}

        def worker(path, key):
            lock = get_file_operation_lock(sb, path)
            lock.acquire()
            barrier.wait(timeout=2)  # both should reach here concurrently
            results[key] = "ok"
            lock.release()

        t1 = threading.Thread(target=worker, args=("/a.txt", "a"))
        t2 = threading.Thread(target=worker, args=("/b.txt", "b"))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert results == {"a": "ok", "b": "ok"}


# ---------------------------------------------------------------------------
# WeakValueDictionary — memory management
# ---------------------------------------------------------------------------


class TestWeakRefCleanup:
    def test_lock_removed_when_no_references(self):
        """Lock should be evicted from WeakValueDictionary after GC when no strong refs remain."""
        import gc

        sb = _make_sandbox("sb-weak")
        # Get the lock and keep only a weak ref
        weak_ref = weakref.ref(get_file_operation_lock(sb, "/weak.txt"))
        # Drop the only strong reference (the local returned value goes out of scope)
        gc.collect()
        # The lock should have been collected; weak ref returns None
        assert weak_ref() is None, "Lock was not collected despite no strong references"

    def test_same_lock_returned_while_referenced(self):
        """Strong reference keeps lock alive and accessible."""
        sb = _make_sandbox()
        lock1 = get_file_operation_lock(sb, "/a.txt")
        lock2 = get_file_operation_lock(sb, "/a.txt")
        assert lock1 is lock2
        # The lock is still strongly referenced by lock1, so it should be in the dict
        lock_key = get_file_operation_lock_key(sb, "/a.txt")
        assert _FILE_OPERATION_LOCKS.get(lock_key) is lock1
