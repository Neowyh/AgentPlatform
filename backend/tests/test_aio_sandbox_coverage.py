"""Coverage tests for ideer.community.aio_sandbox.aio_sandbox — targeting 98%+.

Covers all previously uncovered lines:
- Lines 45, 50-53: base_url and home_dir properties
- Lines 89-91: execute_command exception handler
- Lines 102-107: read_file method (success + error)
- Line 139: download_file max size exceeded
- Lines 168-171: list_dir exception handler
- Lines 188-190: write_file exception handler
- Lines 193-215: glob method (both branches with and without include_dirs)
- Lines 227-270: grep method (with glob, without glob, truncation)
- Lines 279-285: update_file method
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def sandbox():
    """Create an AioSandbox with a mocked client."""
    with patch("ideer.community.aio_sandbox.aio_sandbox.AioSandboxClient"):
        from ideer.community.aio_sandbox.aio_sandbox import AioSandbox

        sb = AioSandbox(id="test-sandbox", base_url="http://localhost:8080")
        return sb


@pytest.fixture()
def sandbox_with_home():
    """Create an AioSandbox with an explicit home_dir."""
    with patch("ideer.community.aio_sandbox.aio_sandbox.AioSandboxClient"):
        from ideer.community.aio_sandbox.aio_sandbox import AioSandbox

        sb = AioSandbox(id="test-sandbox", base_url="http://localhost:8080", home_dir="/home/user")
        return sb


# ===========================================================================
# base_url property (line 45)
# ===========================================================================


class TestBaseUrl:
    def test_base_url_returns_value(self, sandbox):
        assert sandbox.base_url == "http://localhost:8080"

    def test_base_url_is_set_on_init(self):
        with patch("ideer.community.aio_sandbox.aio_sandbox.AioSandboxClient"):
            from ideer.community.aio_sandbox.aio_sandbox import AioSandbox

            sb = AioSandbox(id="test", base_url="http://example.com:9090")
            assert sb.base_url == "http://example.com:9090"


# ===========================================================================
# home_dir property (lines 48-53)
# ===========================================================================


class TestHomeDir:
    def test_home_dir_returns_cached_value(self, sandbox_with_home):
        assert sandbox_with_home.home_dir == "/home/user"

    def test_home_dir_fetches_from_sandbox_when_none(self, sandbox):
        """Lines 50-53: home_dir is None initially, fetched from sandbox."""
        mock_context = SimpleNamespace(home_dir="/root")
        sandbox._client.sandbox.get_context = MagicMock(return_value=mock_context)
        assert sandbox.home_dir == "/root"
        sandbox._client.sandbox.get_context.assert_called_once()

    def test_home_dir_cached_after_first_fetch(self, sandbox):
        """After first fetch, home_dir should be cached."""
        mock_context = SimpleNamespace(home_dir="/root")
        sandbox._client.sandbox.get_context = MagicMock(return_value=mock_context)
        _ = sandbox.home_dir
        _ = sandbox.home_dir
        # Should only be called once because _home_dir is cached
        sandbox._client.sandbox.get_context.assert_called_once()


# ===========================================================================
# execute_command exception handler (lines 89-91)
# ===========================================================================


class TestExecuteCommandException:
    def test_returns_error_string_on_exception(self, sandbox):
        """Lines 89-91: exception caught, returns error string."""
        sandbox._client.shell.exec_command = MagicMock(side_effect=ConnectionError("connection refused"))
        result = sandbox.execute_command("echo hello")
        assert result.startswith("Error:")
        assert "connection refused" in result

    def test_returns_no_output_when_data_is_none(self, sandbox):
        """When result.data is None, returns '(no output)'."""
        sandbox._client.shell.exec_command = MagicMock(return_value=SimpleNamespace(data=None))
        result = sandbox.execute_command("echo hello")
        assert result == "(no output)"

    def test_returns_no_output_when_output_is_empty(self, sandbox):
        """When result.data.output is empty, returns '(no output)'."""
        sandbox._client.shell.exec_command = MagicMock(return_value=SimpleNamespace(data=SimpleNamespace(output="")))
        result = sandbox.execute_command("echo hello")
        assert result == "(no output)"


# ===========================================================================
# read_file method (lines 93-107)
# ===========================================================================


class TestReadFile:
    def test_read_file_success(self, sandbox):
        """Lines 103-104: successful read returns content."""
        sandbox._client.file.read_file = MagicMock(return_value=SimpleNamespace(data=SimpleNamespace(content="file content")))
        result = sandbox.read_file("/mnt/user-data/workspace/test.py")
        assert result == "file content"

    def test_read_file_empty_content(self, sandbox):
        """When content is empty string."""
        sandbox._client.file.read_file = MagicMock(return_value=SimpleNamespace(data=SimpleNamespace(content="")))
        result = sandbox.read_file("/mnt/user-data/workspace/empty.txt")
        assert result == ""

    def test_read_file_data_is_none(self, sandbox):
        """Lines 104: when data is None, returns empty string."""
        sandbox._client.file.read_file = MagicMock(return_value=SimpleNamespace(data=None))
        result = sandbox.read_file("/mnt/user-data/workspace/missing.txt")
        assert result == ""

    def test_read_file_exception(self, sandbox):
        """Lines 105-107: exception caught, returns error string."""
        sandbox._client.file.read_file = MagicMock(side_effect=OSError("file not found"))
        result = sandbox.read_file("/nonexistent.txt")
        assert result.startswith("Error:")
        assert "file not found" in result


# ===========================================================================
# download_file max size exceeded (line 139)
# ===========================================================================


class TestDownloadFileMaxSize:
    def test_raises_oserror_when_exceeding_max_size(self, sandbox):
        """Line 139: file exceeds max download size raises OSError."""
        # Create a chunk that exceeds the 100MB limit
        from ideer.community.aio_sandbox.aio_sandbox import _MAX_DOWNLOAD_SIZE

        big_chunk = b"x" * (_MAX_DOWNLOAD_SIZE + 1)

        sandbox._client.file.download_file = MagicMock(return_value=[big_chunk])

        with pytest.raises(OSError, match="maximum download size"):
            sandbox.download_file("/mnt/user-data/outputs/huge.bin")

    def test_exactly_at_max_size_succeeds(self, sandbox):
        """File exactly at max size should succeed."""
        from ideer.community.aio_sandbox.aio_sandbox import _MAX_DOWNLOAD_SIZE

        # Use chunks that total exactly the limit
        chunk = b"x" * _MAX_DOWNLOAD_SIZE
        sandbox._client.file.download_file = MagicMock(return_value=[chunk])

        result = sandbox.download_file("/mnt/user-data/outputs/exact.bin")
        assert len(result) == _MAX_DOWNLOAD_SIZE


# ===========================================================================
# list_dir exception handler (lines 168-171)
# ===========================================================================


class TestListDirException:
    def test_returns_empty_list_on_exception(self, sandbox):
        """Lines 169-171: exception returns empty list."""
        sandbox._client.shell.exec_command = MagicMock(side_effect=RuntimeError("sandbox down"))
        result = sandbox.list_dir("/mnt/user-data/workspace")
        assert result == []

    def test_returns_empty_list_when_output_is_empty(self, sandbox):
        """When output is empty, returns empty list."""
        sandbox._client.shell.exec_command = MagicMock(return_value=SimpleNamespace(data=SimpleNamespace(output="")))
        result = sandbox.list_dir("/empty/dir")
        assert result == []

    def test_returns_empty_list_when_data_is_none(self, sandbox):
        """When data is None, returns empty list."""
        sandbox._client.shell.exec_command = MagicMock(return_value=SimpleNamespace(data=None))
        result = sandbox.list_dir("/test")
        assert result == []

    def test_parses_multiline_output(self, sandbox):
        """Normal output with multiple lines is parsed correctly."""
        sandbox._client.shell.exec_command = MagicMock(return_value=SimpleNamespace(data=SimpleNamespace(output="/a/file1.py\n/a/file2.py\n/b/dir\n")))
        result = sandbox.list_dir("/test")
        assert "/a/file1.py" in result
        assert "/a/file2.py" in result
        assert "/b/dir" in result

    def test_filters_blank_lines(self, sandbox):
        """Blank lines are filtered out."""
        sandbox._client.shell.exec_command = MagicMock(return_value=SimpleNamespace(data=SimpleNamespace(output="/a\n\n/b\n  \n")))
        result = sandbox.list_dir("/test")
        assert result == ["/a", "/b"]


# ===========================================================================
# write_file exception handler (lines 188-190)
# ===========================================================================


class TestWriteFileException:
    def test_raises_on_write_error(self, sandbox):
        """Lines 189-190: exception is re-raised."""
        sandbox._client.file.write_file = MagicMock(side_effect=OSError("disk full"))
        with pytest.raises(IOError, match="disk full"):
            sandbox.write_file("/mnt/user-data/workspace/test.txt", "content")

    def test_append_mode_concatenates_content(self, sandbox):
        """Lines 183-186: append mode reads existing content first."""
        sandbox._client.file.read_file = MagicMock(return_value=SimpleNamespace(data=SimpleNamespace(content="existing")))
        sandbox._client.file.write_file = MagicMock()

        sandbox.write_file("/mnt/user-data/workspace/log.txt", " appended", append=True)

        sandbox._client.file.write_file.assert_called_once_with(file="/mnt/user-data/workspace/log.txt", content="existing appended")

    def test_append_mode_with_error_existing_content(self, sandbox):
        """Lines 185: when read returns an error, don't prepend content."""
        sandbox._client.file.read_file = MagicMock(return_value="Error: file not found")
        sandbox._client.file.write_file = MagicMock()

        sandbox.write_file("/mnt/user-data/workspace/log.txt", "new content", append=True)

        # Should write just "new content" since existing starts with "Error:"
        call_args = sandbox._client.file.write_file.call_args
        assert call_args[1]["content"] == "new content"

    def test_write_file_no_append(self, sandbox):
        """Normal write (no append) just writes content."""
        sandbox._client.file.write_file = MagicMock()

        sandbox.write_file("/mnt/user-data/workspace/test.txt", "content")

        sandbox._client.file.write_file.assert_called_once_with(file="/mnt/user-data/workspace/test.txt", content="content")


# ===========================================================================
# glob method (lines 192-215)
# ===========================================================================


class TestGlob:
    def test_glob_without_include_dirs(self, sandbox):
        """Lines 193-198: glob without include_dirs uses find_files."""
        mock_result = SimpleNamespace(data=SimpleNamespace(files=["/test/a.py", "/test/b.py", "/test/__pycache__"]))
        sandbox._client.file.find_files = MagicMock(return_value=mock_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", side_effect=lambda p: "__pycache__" in p):
            matches, truncated = sandbox.glob("/test", "**/*.py")

        assert "/test/a.py" in matches
        assert "/test/b.py" in matches
        assert "/test/__pycache__" not in matches
        assert truncated is False

    def test_glob_without_include_dirs_truncated(self, sandbox):
        """Glob results truncated when exceeding max_results."""
        files = [f"/test/f{i}.py" for i in range(10)]
        mock_result = SimpleNamespace(data=SimpleNamespace(files=files))
        sandbox._client.file.find_files = MagicMock(return_value=mock_result)

        matches, truncated = sandbox.glob("/test", "**/*.py", max_results=3)

        assert len(matches) == 3
        assert truncated is True

    def test_glob_with_include_dirs(self, sandbox):
        """Lines 200-215: glob with include_dirs uses list_path."""
        entries = [
            SimpleNamespace(path="/test", is_directory=True),
            SimpleNamespace(path="/test/subdir", is_directory=True),
            SimpleNamespace(path="/test/file.py", is_directory=False),
            SimpleNamespace(path="/test/subdir/other.py", is_directory=False),
            SimpleNamespace(path="/test/subdir/deep", is_directory=True),
        ]
        mock_result = SimpleNamespace(data=SimpleNamespace(files=entries))
        sandbox._client.file.list_path = MagicMock(return_value=mock_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False), patch("ideer.community.aio_sandbox.aio_sandbox.path_matches", side_effect=lambda pat, rel: rel.endswith(".py")):
            matches, truncated = sandbox.glob("/test", "**/*.py", include_dirs=True)

        # Should match file.py and subdir/other.py
        assert "/test/file.py" in matches
        assert "/test/subdir/other.py" in matches
        assert truncated is False

    def test_glob_with_include_dirs_truncated(self, sandbox):
        """Glob with include_dirs truncates at max_results."""
        entries = [SimpleNamespace(path=f"/test/f{i}.py", is_directory=False) for i in range(10)]
        mock_result = SimpleNamespace(data=SimpleNamespace(files=entries))
        sandbox._client.file.list_path = MagicMock(return_value=mock_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False), patch("ideer.community.aio_sandbox.aio_sandbox.path_matches", return_value=True):
            matches, truncated = sandbox.glob("/test", "**/*.py", include_dirs=True, max_results=3)

        assert len(matches) == 3
        assert truncated is True

    def test_glob_with_include_dirs_root_slash(self, sandbox):
        """Lines 203-204: root_path handling when path is '/'."""
        entries = [
            SimpleNamespace(path="/file.py", is_directory=False),
        ]
        mock_result = SimpleNamespace(data=SimpleNamespace(files=entries))
        sandbox._client.file.list_path = MagicMock(return_value=mock_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False), patch("ideer.community.aio_sandbox.aio_sandbox.path_matches", return_value=True):
            matches, truncated = sandbox.glob("/", "**/*.py", include_dirs=True)

        assert "/file.py" in matches

    def test_glob_with_include_dirs_skips_non_root_entries(self, sandbox):
        """Lines 206-208: entries outside root path are skipped."""
        entries = [
            SimpleNamespace(path="/other/file.py", is_directory=False),
            SimpleNamespace(path="/test/file.py", is_directory=False),
        ]
        mock_result = SimpleNamespace(data=SimpleNamespace(files=entries))
        sandbox._client.file.list_path = MagicMock(return_value=mock_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False), patch("ideer.community.aio_sandbox.aio_sandbox.path_matches", return_value=True):
            matches, truncated = sandbox.glob("/test", "**/*.py", include_dirs=True)

        assert "/other/file.py" not in matches
        assert "/test/file.py" in matches

    def test_glob_find_files_returns_none(self, sandbox):
        """When find_files returns None data."""
        mock_result = SimpleNamespace(data=None)
        sandbox._client.file.find_files = MagicMock(return_value=mock_result)

        matches, truncated = sandbox.glob("/test", "**/*.py")
        assert matches == []
        assert truncated is False

    def test_glob_find_files_returns_empty_files(self, sandbox):
        """When find_files returns empty files list."""
        mock_result = SimpleNamespace(data=SimpleNamespace(files=[]))
        sandbox._client.file.find_files = MagicMock(return_value=mock_result)

        matches, truncated = sandbox.glob("/test", "**/*.py")
        assert matches == []


# ===========================================================================
# grep method (lines 217-270)
# ===========================================================================


class TestGrep:
    def test_grep_with_glob_filter(self, sandbox):
        """Lines 237-238: grep with glob filter uses find_files."""
        find_result = SimpleNamespace(data=SimpleNamespace(files=["/test/a.py", "/test/b.py"]))
        sandbox._client.file.find_files = MagicMock(return_value=find_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=[1, 3], matches=["hello", "world"]))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            with patch("ideer.community.aio_sandbox.aio_sandbox.truncate_line", side_effect=lambda x: x):
                matches, truncated = sandbox.grep("/test", "hello", glob="**/*.py")

        assert len(matches) == 4  # 2 matches per file, 2 files
        assert truncated is False

    def test_grep_without_glob_filter(self, sandbox):
        """Lines 240-242: grep without glob uses list_path."""
        entries = [
            SimpleNamespace(path="/test/a.py", is_directory=False),
            SimpleNamespace(path="/test/subdir", is_directory=True),
        ]
        list_result = SimpleNamespace(data=SimpleNamespace(files=entries))
        sandbox._client.file.list_path = MagicMock(return_value=list_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["found it"]))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            with patch("ideer.community.aio_sandbox.aio_sandbox.truncate_line", side_effect=lambda x: x):
                matches, truncated = sandbox.grep("/test", "found")

        # Only a.py should be searched (subdir is_directory=True is filtered)
        assert len(matches) == 1

    def test_grep_skips_ignored_paths(self, sandbox):
        """Lines 248-249: ignored paths are skipped."""
        find_result = SimpleNamespace(data=SimpleNamespace(files=["/test/a.py", "/test/__pycache__/c.py"]))
        sandbox._client.file.find_files = MagicMock(return_value=find_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["hello"]))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", side_effect=lambda p: "__pycache__" in p):
            matches, truncated = sandbox.grep("/test", "hello", glob="**/*.py")

        # search_in_file should only be called once (for a.py)
        assert sandbox._client.file.search_in_file.call_count == 1

    def test_grep_truncates_at_max_results(self, sandbox):
        """Lines 266-268: truncation when reaching max_results."""
        files = [f"/test/f{i}.py" for i in range(10)]
        find_result = SimpleNamespace(data=SimpleNamespace(files=files))
        sandbox._client.file.find_files = MagicMock(return_value=find_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["match"]))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            with patch("ideer.community.aio_sandbox.aio_sandbox.truncate_line", side_effect=lambda x: x):
                matches, truncated = sandbox.grep("/test", "match", glob="**/*.py", max_results=3)

        assert len(matches) == 3
        assert truncated is True

    def test_grep_literal_mode(self, sandbox):
        """Lines 229-233: literal mode escapes regex."""
        find_result = SimpleNamespace(data=SimpleNamespace(files=["/test/a.py"]))
        sandbox._client.file.find_files = MagicMock(return_value=find_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["found (literal)"]))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            with patch("ideer.community.aio_sandbox.aio_sandbox.truncate_line", side_effect=lambda x: x):
                matches, truncated = sandbox.grep("/test", "(literal)", glob="**/*.py", literal=True)

        assert len(matches) == 1

    def test_grep_case_sensitive(self, sandbox):
        """Lines 233-234: case sensitive mode."""
        find_result = SimpleNamespace(data=SimpleNamespace(files=["/test/a.py"]))
        sandbox._client.file.find_files = MagicMock(return_value=find_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["Hello"]))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            with patch("ideer.community.aio_sandbox.aio_sandbox.truncate_line", side_effect=lambda x: x):
                matches, truncated = sandbox.grep("/test", "Hello", glob="**/*.py", case_sensitive=True)

        assert len(matches) == 1

    def test_grep_invalid_regex_raises(self, sandbox):
        """Lines 232: invalid regex raises re.error."""
        with pytest.raises(re.error):
            sandbox.grep("/test", "[invalid", glob="**/*.py")

    def test_grep_search_result_data_none(self, sandbox):
        """Lines 253: search result data is None, skipped."""
        find_result = SimpleNamespace(data=SimpleNamespace(files=["/test/a.py"]))
        sandbox._client.file.find_files = MagicMock(return_value=find_result)

        search_result = SimpleNamespace(data=None)
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            matches, truncated = sandbox.grep("/test", "pattern", glob="**/*.py")

        assert matches == []
        assert truncated is False

    def test_grep_line_numbers_and_matches_empty(self, sandbox):
        """When line_numbers and matches are empty/None."""
        find_result = SimpleNamespace(data=SimpleNamespace(files=["/test/a.py"]))
        sandbox._client.file.find_files = MagicMock(return_value=find_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=None, matches=None))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            matches, truncated = sandbox.grep("/test", "pattern", glob="**/*.py")

        assert matches == []

    def test_grep_non_integer_line_number(self, sandbox):
        """Line 262: non-integer line_number defaults to 0."""
        find_result = SimpleNamespace(data=SimpleNamespace(files=["/test/a.py"]))
        sandbox._client.file.find_files = MagicMock(return_value=find_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=["not_int"], matches=["hello"]))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            with patch("ideer.community.aio_sandbox.aio_sandbox.truncate_line", side_effect=lambda x: x):
                matches, truncated = sandbox.grep("/test", "hello", glob="**/*.py")

        assert len(matches) == 1
        assert matches[0].line_number == 0

    def test_grep_without_glob_filters_directories(self, sandbox):
        """Lines 242: list_path results filter out directories."""
        entries = [
            SimpleNamespace(path="/test/a.py", is_directory=False),
            SimpleNamespace(path="/test/subdir", is_directory=True),
        ]
        list_result = SimpleNamespace(data=SimpleNamespace(files=entries))
        sandbox._client.file.list_path = MagicMock(return_value=list_result)

        search_result = SimpleNamespace(data=SimpleNamespace(line_numbers=[1], matches=["found"]))
        sandbox._client.file.search_in_file = MagicMock(return_value=search_result)

        with patch("ideer.community.aio_sandbox.aio_sandbox.should_ignore_path", return_value=False):
            with patch("ideer.community.aio_sandbox.aio_sandbox.truncate_line", side_effect=lambda x: x):
                matches, truncated = sandbox.grep("/test", "found")

        # Only a.py should be searched, not subdir
        assert sandbox._client.file.search_in_file.call_count == 1


# ===========================================================================
# update_file method (lines 272-285)
# ===========================================================================


class TestUpdateFile:
    def test_update_file_encodes_to_base64(self, sandbox):
        """Lines 281-282: binary content encoded as base64."""
        sandbox._client.file.write_file = MagicMock()

        sandbox.update_file("/mnt/user-data/outputs/data.bin", b"\x00\x01\x02")

        import base64

        expected_b64 = base64.b64encode(b"\x00\x01\x02").decode("utf-8")
        sandbox._client.file.write_file.assert_called_once_with(
            file="/mnt/user-data/outputs/data.bin",
            content=expected_b64,
            encoding="base64",
        )

    def test_update_file_raises_on_error(self, sandbox):
        """Lines 284-285: exception is re-raised."""
        sandbox._client.file.write_file = MagicMock(side_effect=OSError("write failed"))

        with pytest.raises(IOError, match="write failed"):
            sandbox.update_file("/mnt/user-data/outputs/data.bin", b"data")


# ===========================================================================
# download_file additional edge cases
# ===========================================================================


class TestDownloadFileEdgeCases:
    def test_download_exceeds_max_with_multiple_chunks(self, sandbox):
        """Multiple chunks that together exceed the max size."""
        from ideer.community.aio_sandbox.aio_sandbox import _MAX_DOWNLOAD_SIZE

        chunk_size = (_MAX_DOWNLOAD_SIZE // 2) + 1
        chunks = [b"x" * chunk_size, b"x" * chunk_size]

        sandbox._client.file.download_file = MagicMock(return_value=iter(chunks))

        with pytest.raises(OSError, match="maximum download size"):
            sandbox.download_file("/mnt/user-data/outputs/large.bin")

    def test_download_path_traversal_backslash(self, sandbox):
        """Path traversal with backslashes is rejected."""
        sandbox._client.file.download_file = MagicMock()

        with pytest.raises(PermissionError, match="path traversal"):
            sandbox.download_file("/mnt/user-data/..\\..\\etc\\passwd")

        sandbox._client.file.download_file.assert_not_called()

    def test_download_exactly_virtual_prefix(self, sandbox):
        """Exactly /mnt/user-data (the prefix itself) is allowed."""
        sandbox._client.file.download_file = MagicMock(return_value=[b"data"])

        result = sandbox.download_file("/mnt/user-data")
        assert result == b"data"
