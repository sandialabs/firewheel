import random
import shutil
import filecmp
import hashlib
import tarfile
import traceback
from time import sleep
from typing import Any
from pathlib import Path
from functools import wraps as _wraps

from rich.console import Console


def unescape_embedded_json(escaped_json: str) -> str:
    """Convert embedded escaped JSON text into normal JSON text."""
    return escaped_json.replace(r"\\", "\\").replace(r"\"", '"')


def escape_embedded_json(json_text: str, is_mesh_command: bool) -> str:
    """Escape JSON text for reinsertion into a launch command line."""
    if is_mesh_command:
        return json_text.replace('"', r"\\\"")
    return json_text.replace('"', r"\"")


def files_are_identical(source: Path, destination: Path) -> bool:
    """Return whether two files are byte-for-byte identical.

    Args:
        source (Path): Source file path.
        destination (Path): Destination file path.

    Returns:
        bool: True if both files exist and have identical contents, otherwise False.
    """
    if not source.is_file() or not destination.is_file():
        return False
    return filecmp.cmp(source, destination, shallow=False)


def directories_are_identical(source: Path, destination: Path) -> bool:
    """Return whether two directory trees are identical.

    Args:
        source (Path): Source directory path.
        destination (Path): Destination directory path.

    Returns:
        bool: True if the directory trees have identical structure and file contents,
        otherwise False.
    """
    if not source.is_dir() or not destination.is_dir():
        return False

    comparison = filecmp.dircmp(source, destination)

    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False

    _, mismatch, errors = filecmp.cmpfiles(
        source,
        destination,
        comparison.common_files,
        shallow=False,
    )
    if mismatch or errors:
        return False

    for common_dir in comparison.common_dirs:
        if not directories_are_identical(source / common_dir, destination / common_dir):
            return False

    return True


def copytree_if_needed(source: Path, destination: Path, force: bool) -> bool:
    """Copy a directory tree only when needed.

    If the destination exists and is identical to the source, no action is taken.

    Args:
        source (Path): Source directory.
        destination (Path): Destination directory.
        force (bool): Whether differing existing content may be overwritten.

    Returns:
        bool: True if content was copied or overwritten, False if skipped because the
        destination already matched the source.

    Raises:
        FileExistsError: If destination exists with different contents and
            ``force`` is False.
        OSError: If copying or deleting fails.
    """
    if not destination.exists():
        shutil.copytree(source, destination)
        return True

    if directories_are_identical(source, destination):
        return False

    if not force:
        raise FileExistsError(
            f"Destination already exists with different contents: {destination}"
        )

    if destination.is_dir():
        shutil.rmtree(destination)
    else:
        destination.unlink()

    shutil.copytree(source, destination)
    return True


def copyfile_if_needed(source: Path, destination: Path, force: bool) -> bool:
    """Copy a file only when needed.

    If the destination exists and is identical to the source, no action is taken.

    Args:
        source (Path): Source file.
        destination (Path): Destination file.
        force (bool): Whether differing existing content may be overwritten.

    Returns:
        bool: True if content was copied or overwritten, False if skipped because the
        destination already matched the source.

    Raises:
        FileExistsError: If destination exists with different contents and
            ``force`` is False.
        OSError: If copying or deleting fails.
    """
    if not destination.exists():
        shutil.copy2(source, destination)
        return True

    if files_are_identical(source, destination):
        return False

    if not force:
        raise FileExistsError(
            f"Destination already exists with different contents: {destination}"
        )

    if destination.is_dir():
        shutil.rmtree(destination)
    else:
        destination.unlink()

    shutil.copy2(source, destination)
    return True


def print_phase_header(console, title: str) -> None:
    """Print a restore phase header.

    Args:
        console (Console): The console to print to.
        title (str): Phase title to display.
    """
    console.rule(f"[bold blue]{title}[/bold blue]")


def print_success(console, message: str) -> None:
    """Print a success message.

    Args:
        console (Console): The console to print to.
        message (str): Message to display.
    """
    console.print(f"[green]✓ {message}[/green]")


def print_reused(console, message: str) -> None:
    """Print a reused/skipped message.

    Args:
        console (Console): The console to print to.
        message (str): Message to display.
    """
    console.print(f"[yellow]↺ {message}[/yellow]")


def print_error(console, message: str) -> None:
    """Print an error message.

    Args:
        console (Console): The console to print to.
        message (str): Message to display.
    """
    console.print(f"[red]✗ {message}[/red]")


def print_result_card(console, title: str, lines: list[tuple[str, str]]) -> None:
    """Print a concise result card.

    Args:
        console (Console): The console to print to.
        title (str): Card title.
        lines (list[tuple[str, str]]): Sequence of key/value pairs to display.
    """
    console.print(f"[bold]{title}[/bold]")
    for key, value in lines:
        console.print(f"  [cyan]{key:<26}[/cyan] {value}")


def render_rich_string(text):
    """
    Convert a string with :py:mod:`rich` markup to standard string with ANSI sequences.
    This is useful for printing without the :py:class:`rich.console.Console`.

    Note:
        Adapted from: https://github.com/Textualize/rich/issues/3152#issuecomment-1759770089

    Args:
        text (str): The text to convert.

    Returns:
        str: A string with ANSI markup as defined by :py:mod:`rich`.
    """
    console = Console(file=None, highlight=False, color_system="standard")
    with console.capture() as capture:
        console.print(text, soft_wrap=True, end="")
    return capture.get()


def badpath(path: str, base: Path) -> bool:
    """Check whether a path escapes the provided base directory.

    Args:
        path (str): Proposed extraction path.
        base (Path): Intended extraction base directory.

    Returns:
        bool: True if the resolved path escapes the base directory, otherwise False.
    """
    joint = (base / path).resolve()
    return not str(joint).startswith(str(base.resolve()))


def badlink(info: tarfile.TarInfo, base: Path) -> bool:
    """Check whether a tar link target escapes the provided base directory.

    Args:
        info (tarfile.TarInfo): Tar file member to inspect.
        base (Path): Intended extraction base directory.

    Returns:
        bool: True if the resolved link target escapes the base directory, otherwise
        False.
    """
    link_path = (base / Path(info.name).parent).resolve()
    return badpath(info.linkname, link_path)


def get_safe_tarfile_members(
    tarfile_obj: tarfile.TarFile,
    base: Path,
) -> list[tarfile.TarInfo]:
    """Return tar members considered safe to extract under a base directory.

    Args:
        tarfile_obj (tarfile.TarFile): Open tar archive.
        base (Path): Intended extraction base directory.

    Returns:
        list[tarfile.TarInfo]: List of safe tar members.
    """
    resolved_base = base.resolve()
    result: list[tarfile.TarInfo] = []
    console = Console()

    for member in tarfile_obj.getmembers():
        if badpath(member.name, resolved_base):
            console.print(f"[b red]{member.name} is blocked: illegal path[/b red]")
        elif member.issym() and badlink(member, resolved_base):
            console.print(
                f"[b red]{member.name} is blocked: symlink to [cyan]{member.linkname}[/cyan][/b red]"
            )
        elif member.islnk() and badlink(member, resolved_base):
            console.print(
                f"[b red]{member.name} is blocked: hard link to [cyan]{member.linkname}[/cyan][/b red]"
            )
        else:
            result.append(member)

    return result


def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0).
    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.

    Copied from `distutils <https://docs.python.org/3.9/distutils/apiref.html>`_
    which has since been deprecated.

    Arguments:
        val (str): A string to check if it is a boolean value.

    Returns:
        int: 1 if the value is True and 0 if the value is False.

    Raises:
        ValueError: If an invalid input is provided.
    """
    val = val.lower()
    if val in {"y", "yes", "t", "true", "on", "1"}:
        return 1
    if val in {"n", "no", "f", "false", "off", "0"}:
        return 0

    raise ValueError(f"Invalid truth value {val}")


def hash_file(fname: str) -> str:
    """
    A relatively efficient way of hashing a file
    https://stackoverflow.com/a/3431838.
    Through various performance tests, we found that SHA1 is currently the fastest
    hashlib function. We also found that SHA-1 performance improved by using a
    chunk size of 1048576.

    Args:
        fname (str): The name of the file to hash.

    Returns:
        str: The hash of the file.
    """
    # The following hash is not used in any security context and
    # collisions are acceptable.
    hash_func = hashlib.sha1()  # noqa: S324
    with open(fname, "rb") as fopened:
        for chunk in iter(lambda: fopened.read(1048576), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def retry(num_tries, exceptions=None, base_delay=10, exp_factor=2):
    """
    This function provides a decorator which enables automatic retrying of
    functions which make connections to the FileStore and fail due to timeout errors.
    This code was adapted from:
    https://dzone.com/articles/pymongo-pointers-how-to-make-robust-and-highly-ava-1

    Args:
        num_tries (int): The number of times to try the function.
        exceptions (tuple): A tuple of exceptions to except.
        base_delay (int): The constant amount of time to sleep between attempts.
        exp_factor (int): The exponential amount of time to sleep between attempts.
            When set to 1, there will be no exponential increase in sleep times.

    Returns:
        The decorator function.
    """

    # If no exceptions were provided, we will default to any Exception.
    if not exceptions:
        exceptions = (Exception,)

    def decorator(func):
        """
        This is the decorator function which will be returned. We need to use wraps
        to preserve the docstrings of the original functions in Sphinx as noted in
        this issue:
        https://github.com/sphinx-doc/sphinx/issues/3783#issuecomment-303099039

        Args:
            func (func): The function to decorate.

        Returns:
            The ``f_retry`` function.
        """

        @_wraps(func)
        def f_retry(*args: Any, **kwargs: Any):
            """
            The retry loop which attempts the function ``num_tries`` times
            and will catch exceptions passed into exceptions, then sleep
            for a random time uniformly sampled between 1 and
            base_delay*exp_factor**(attempt) seconds before retrying.

            Args:
                *args (Any): Any arguments to the function.
                **kwargs (Any): Any keyword arguments to the function.

            Returns:
                The passed in function.

            Raises:
                exceptions: It may raise any of the given exceptions.
            """
            try:
                # Try to get the log from the first argument (normally self).
                log_func = args[0].log.debug
            except (IndexError, AttributeError):
                # If we can't get log.info from the first argument, fall back to print.
                log_func = print
            rand = random.SystemRandom()
            # Index from 1 to make logs more human friendly.
            for i in range(1, num_tries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exp:
                    sleep_time = rand.randint(1, base_delay * exp_factor**i)
                    log_func(
                        f"function {func.__name__} hit exception on try #{i}/{num_tries}\n{exp}"
                    )
                    tb_str = "".join(traceback.format_tb(exp.__traceback__))
                    log_func(tb_str)
                    if i == num_tries:
                        raise
                    log_func(f"sleeping for {sleep_time} seconds.")
                    sleep(sleep_time)
                    continue
            return None

        return f_retry

    return decorator
