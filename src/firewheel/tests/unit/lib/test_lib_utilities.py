# test_lib_utilities.py
"""Unit tests for :mod:`firewheel.lib.utilities`."""

from __future__ import annotations

import io
import tarfile
import tempfile
import multiprocessing
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from firewheel.lib.utilities import (
    retry,
    badlink,
    badpath,
    hash_file,
    strtobool,
    print_error,
    print_reused,
    print_success,
    print_result_card,
    copyfile_if_needed,
    copytree_if_needed,
    print_phase_header,
    render_rich_string,
    files_are_identical,
    escape_embedded_json,
    unescape_embedded_json,
    manage_queueing_process,
    get_safe_tarfile_members,
    directories_are_identical,
)


def test_unescape_embedded_json() -> None:
    """Verify escaped embedded JSON is normalized."""
    escaped = r"{\"key\": \"value\", \"path\": \"C:\\tmp\"}"
    assert unescape_embedded_json(escaped) == '{"key": "value", "path": "C:\\tmp"}'


@pytest.mark.parametrize(
    ("is_mesh_command", "expected"),
    [
        (False, r"{\"key\": \"value\"}"),
        (True, r"{\\\"key\\\": \\\"value\\\"}"),
    ],
)
def test_escape_embedded_json(is_mesh_command: bool, expected: str) -> None:
    """Verify JSON escaping behavior for both command contexts."""
    assert escape_embedded_json('{"key": "value"}', is_mesh_command) == expected


def test_files_are_identical(tmp_path: Path) -> None:
    """Verify file content comparison is deep and correct."""
    source = tmp_path / "source.txt"
    dest = tmp_path / "dest.txt"
    source.write_text("same", encoding="utf-8")
    dest.write_text("same", encoding="utf-8")

    assert files_are_identical(source, dest) is True

    dest.write_text("different", encoding="utf-8")
    assert files_are_identical(source, dest) is False


def test_files_are_identical_missing_path(tmp_path: Path) -> None:
    """Verify missing files are not considered identical."""
    source = tmp_path / "source.txt"
    source.write_text("data", encoding="utf-8")
    missing = tmp_path / "missing.txt"

    assert files_are_identical(source, missing) is False


def test_directories_are_identical(tmp_path: Path) -> None:
    """Verify recursive directory comparison succeeds for matching trees."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    (left / "sub").mkdir(parents=True)
    (right / "sub").mkdir(parents=True)

    (left / "a.txt").write_text("a", encoding="utf-8")
    (right / "a.txt").write_text("a", encoding="utf-8")
    (left / "sub" / "b.txt").write_text("b", encoding="utf-8")
    (right / "sub" / "b.txt").write_text("b", encoding="utf-8")

    assert directories_are_identical(left, right) is True


def test_directories_are_identical_with_ignore(tmp_path: Path) -> None:
    """Verify ignored names are skipped at all recursion levels."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()

    (left / "same.txt").write_text("same", encoding="utf-8")
    (right / "same.txt").write_text("same", encoding="utf-8")
    (left / "ignore.me").write_text("left", encoding="utf-8")
    (right / "ignore.me").write_text("right", encoding="utf-8")

    assert directories_are_identical(left, right, ignore={"ignore.me"}) is True


def test_directories_are_identical_false_when_mismatch(tmp_path: Path) -> None:
    """Verify directory comparison fails on differing file contents."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()

    (left / "same_name.txt").write_text("one", encoding="utf-8")
    (right / "same_name.txt").write_text("two", encoding="utf-8")

    assert directories_are_identical(left, right) is False


def test_copytree_if_needed_copy_when_missing(tmp_path: Path) -> None:
    """Verify a missing destination directory is copied."""
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    (source / "file.txt").write_text("data", encoding="utf-8")

    assert copytree_if_needed(source, dest, force=False) is True
    assert (dest / "file.txt").read_text(encoding="utf-8") == "data"


def test_copytree_if_needed_skip_when_identical(tmp_path: Path) -> None:
    """Verify copying is skipped when destination already matches source."""
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()
    (source / "file.txt").write_text("data", encoding="utf-8")
    (dest / "file.txt").write_text("data", encoding="utf-8")

    assert copytree_if_needed(source, dest, force=False) is False


def test_copytree_if_needed_raises_without_force(tmp_path: Path) -> None:
    """Verify differing existing destination raises when force is disabled."""
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()
    (source / "file.txt").write_text("source", encoding="utf-8")
    (dest / "file.txt").write_text("dest", encoding="utf-8")

    with pytest.raises(FileExistsError):
        copytree_if_needed(source, dest, force=False)


def test_copytree_if_needed_overwrite_with_force(tmp_path: Path) -> None:
    """Verify differing destination is replaced when force is enabled."""
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()
    (source / "file.txt").write_text("source", encoding="utf-8")
    (dest / "file.txt").write_text("dest", encoding="utf-8")

    assert copytree_if_needed(source, dest, force=True) is True
    assert (dest / "file.txt").read_text(encoding="utf-8") == "source"


def test_copyfile_if_needed_copy_when_missing(tmp_path: Path) -> None:
    """Verify a missing destination file is copied."""
    source = tmp_path / "source.txt"
    dest = tmp_path / "dest.txt"
    source.write_text("data", encoding="utf-8")

    assert copyfile_if_needed(source, dest, force=False) is True
    assert dest.read_text(encoding="utf-8") == "data"


def test_copyfile_if_needed_skip_when_identical(tmp_path: Path) -> None:
    """Verify copying is skipped for identical files."""
    source = tmp_path / "source.txt"
    dest = tmp_path / "dest.txt"
    source.write_text("data", encoding="utf-8")
    dest.write_text("data", encoding="utf-8")

    assert copyfile_if_needed(source, dest, force=False) is False


def test_copyfile_if_needed_raises_without_force(tmp_path: Path) -> None:
    """Verify differing destination file raises when force is disabled."""
    source = tmp_path / "source.txt"
    dest = tmp_path / "dest.txt"
    source.write_text("source", encoding="utf-8")
    dest.write_text("dest", encoding="utf-8")

    with pytest.raises(FileExistsError):
        copyfile_if_needed(source, dest, force=False)


def test_copyfile_if_needed_overwrite_with_force(tmp_path: Path) -> None:
    """Verify differing destination file is overwritten with force enabled."""
    source = tmp_path / "source.txt"
    dest = tmp_path / "dest.txt"
    source.write_text("source", encoding="utf-8")
    dest.write_text("dest", encoding="utf-8")

    assert copyfile_if_needed(source, dest, force=True) is True
    assert dest.read_text(encoding="utf-8") == "source"


def test_print_helpers_and_result_card() -> None:
    """Verify rich console print helpers emit expected text."""
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None)

    print_phase_header(console, "Phase")
    print_success(console, "ok")
    print_reused(console, "reused")
    print_error(console, "bad")
    print_result_card(console, "Summary", [("Key", "Value")])

    output = stream.getvalue()
    assert "Phase" in output
    assert "ok" in output
    assert "reused" in output
    assert "bad" in output
    assert "Summary" in output
    assert "Key" in output
    assert "Value" in output


def test_render_rich_string_contains_ansi() -> None:
    """Verify rich markup is rendered to ANSI text."""
    rendered = render_rich_string("[bold red]hello[/bold red]")
    assert "hello" in rendered
    assert "\x1b[" in rendered


def test_badpath() -> None:
    """Verify path traversal detection for extraction paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        assert badpath("safe/file.txt", base) is False
        assert badpath("../escape.txt", base) is True


def test_badlink() -> None:
    """Verify link traversal detection for tar members."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        safe = tarfile.TarInfo(name="dir/link")
        safe.linkname = "target.txt"

        bad = tarfile.TarInfo(name="dir/link")
        bad.linkname = "../../escape.txt"

        assert badlink(safe, base) is False
        assert badlink(bad, base) is True


def test_get_safe_tarfile_members_blocks_unsafe_members(tmp_path: Path) -> None:
    """Verify unsafe tar members are excluded from extraction."""
    tar_path = tmp_path / "archive.tar"
    safe_file = tmp_path / "safe.txt"
    safe_file.write_text("safe", encoding="utf-8")

    with tarfile.open(tar_path, "w") as tar_handle:
        tar_handle.add(safe_file, arcname="safe.txt")

        bad_member = tarfile.TarInfo("../evil.txt")
        bad_member.size = 0
        tar_handle.addfile(bad_member)

        bad_symlink = tarfile.TarInfo("link.txt")
        bad_symlink.type = tarfile.SYMTYPE
        bad_symlink.linkname = "../../evil.txt"
        tar_handle.addfile(bad_symlink)

    with tarfile.open(tar_path, "r") as tar_handle:
        members = get_safe_tarfile_members(tar_handle, tmp_path / "extract")

    names = [member.name for member in members]
    assert "safe.txt" in names
    assert "../evil.txt" not in names
    assert "link.txt" not in names


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("y", 1),
        ("yes", 1),
        ("TRUE", 1),
        ("off", 0),
        ("0", 0),
    ],
)
def test_strtobool_valid(value: str, expected: int) -> None:
    """Verify supported boolean string values are converted correctly."""
    assert strtobool(value) == expected


def test_strtobool_invalid() -> None:
    """Verify invalid boolean strings raise a ValueError."""
    with pytest.raises(ValueError):
        strtobool("maybe")


def test_hash_file(tmp_path: Path) -> None:
    """Verify file hashing is stable and non-empty."""
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"abcdef")

    first = hash_file(str(file_path))
    second = hash_file(str(file_path))

    assert first == second
    assert first


def test_retry_success_after_retries() -> None:
    """Verify retry decorator retries transient failures and succeeds."""
    calls = {"count": 0}

    @retry(3, exceptions=(ValueError,), base_delay=1, exp_factor=1)
    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("temporary")
        return "ok"

    with patch("firewheel.lib.utilities.sleep") as mock_sleep:
        assert flaky() == "ok"

    assert calls["count"] == 3
    assert mock_sleep.call_count == 2


def test_retry_raises_on_final_attempt() -> None:
    """Verify retry decorator re-raises after exhausting attempts."""

    @retry(2, exceptions=(ValueError,), base_delay=1, exp_factor=1)
    def always_fail() -> None:
        raise ValueError("boom")

    with patch("firewheel.lib.utilities.sleep"):
        with pytest.raises(ValueError):
            always_fail()


def test_retry_uses_object_logger_when_available() -> None:
    """Verify retry decorator uses args[0].log.debug when present."""

    class HasLogger:
        """Helper class with a logger for retry tests."""

        def __init__(self) -> None:
            self.log = Mock()
            self.log.debug = Mock()
            self.calls = 0

        @retry(2, exceptions=(RuntimeError,), base_delay=1, exp_factor=1)
        def run(self) -> str:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("fail once")
            return "done"

    obj = HasLogger()
    with patch("firewheel.lib.utilities.sleep"):
        assert obj.run() == "done"

    assert obj.log.debug.called


def test_directories_are_identical_false_if_not_directories(tmp_path: Path) -> None:
    """Verify non-directory inputs return False."""
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("a", encoding="utf-8")
    destination.write_text("b", encoding="utf-8")

    assert directories_are_identical(source, destination) is False


def test_copytree_if_needed_replaces_file_destination(tmp_path: Path) -> None:
    """Verify force mode replaces a non-directory destination."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")

    destination = tmp_path / "destination"
    destination.write_text("old", encoding="utf-8")

    assert copytree_if_needed(source, destination, force=True) is True
    assert destination.is_dir()
    assert (destination / "file.txt").read_text(encoding="utf-8") == "payload"


def test_copyfile_if_needed_replaces_directory_destination(tmp_path: Path) -> None:
    """Verify force mode replaces a directory destination."""
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")

    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "nested.txt").write_text("old", encoding="utf-8")

    assert copyfile_if_needed(source, destination, force=True) is True
    assert destination.is_file()
    assert destination.read_text(encoding="utf-8") == "payload"


def test_files_are_identical_false_if_destination_is_directory(tmp_path: Path) -> None:
    """Verify file comparison returns False for non-file destination."""
    source = tmp_path / "source.txt"
    source.write_text("data", encoding="utf-8")
    destination = tmp_path / "dest"
    destination.mkdir()

    assert files_are_identical(source, destination) is False


def test_retry_defaults_to_exception_tuple() -> None:
    """Verify retry defaults to catching Exception when not provided."""
    calls = {"count": 0}

    @retry(2, base_delay=1, exp_factor=1)
    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return "ok"

    with patch("firewheel.lib.utilities.sleep"):
        assert flaky() == "ok"
    assert calls["count"] == 2


def test_retry_does_not_catch_unlisted_exception() -> None:
    """Verify retry does not catch exceptions outside the configured tuple."""

    @retry(3, exceptions=(ValueError,), base_delay=1, exp_factor=1)
    def fail() -> None:
        raise RuntimeError("not caught")

    with pytest.raises(RuntimeError):
        fail()


def test_badpath_with_absolute_escape(tmp_path: Path) -> None:
    """Verify absolute paths outside the base are rejected."""
    assert badpath("/etc/passwd", tmp_path) is True


def test_badlink_with_nested_parent_escape(tmp_path: Path) -> None:
    """Verify tar links escaping via parent traversal are rejected."""
    info = tarfile.TarInfo(name="nested/link")
    info.linkname = "../../../etc/passwd"
    assert badlink(info, tmp_path) is True


class TestManageQueueingProcess:
    """Unit tests for task queue process manager."""

    @pytest.fixture
    def mock_queue(self):
        return Mock()

    @pytest.fixture
    def mock_process(self):
        return Mock()

    @pytest.fixture
    def mock_context(self, mock_queue, mock_process):
        context = Mock()
        context.Queue.return_value = mock_queue
        context.Process.return_value = mock_process
        return context

    @pytest.fixture(autouse=True)
    def mock_get_context(self, mock_context):
        with patch.object(multiprocessing, "get_context", return_value=mock_context) as mocked:
            yield mocked

    def test_yields_process_and_queue_after_start(
        self, mock_get_context, mock_context, mock_queue, mock_process
    ):
        with manage_queueing_process("target", "arg1", "arg2") as (process, queue):
            assert process is mock_process
            assert queue is mock_queue

        mock_get_context.assert_called_once_with()
        mock_context.Queue.assert_called_once_with()
        mock_context.Process.assert_called_once_with(
            target="target",
            args=(mock_queue, "arg1", "arg2"),
        )
        mock_process.start.assert_called_once_with()

    def test_terminates_and_joins_when_process_is_alive_on_exit(
        self, mock_process
    ):
        mock_process.is_alive.return_value = True

        with manage_queueing_process("target"):
            pass

        mock_process.start.assert_called_once_with()
        mock_process.is_alive.assert_called_once_with()
        mock_process.terminate.assert_called_once_with()
        mock_process.join.assert_called_once_with()

    def test_does_not_terminate_or_join_when_process_not_alive_on_exit(
        self, mock_process
    ):
        mock_process.is_alive.return_value = False

        with manage_queueing_process("target"):
            pass

        mock_process.start.assert_called_once_with()
        mock_process.is_alive.assert_called_once_with()
        mock_process.terminate.assert_not_called()
        mock_process.join.assert_not_called()

    def test_cleanup_still_happens_when_exception_raised_inside_context(
        self, mock_process
    ):
        mock_process.is_alive.return_value = True

        with pytest.raises(RuntimeError, match="FAILURE"):
            with manage_queueing_process("target"):
                raise RuntimeError("FAILURE")

        mock_process.start.assert_called_once_with()
        mock_process.is_alive.assert_called_once_with()
        mock_process.terminate.assert_called_once_with()
        mock_process.join.assert_called_once_with()
