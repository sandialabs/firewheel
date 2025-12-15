import random
import hashlib
import traceback
from time import sleep
from pathlib import Path
from functools import wraps as _wraps

from rich.console import Console


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


def badpath(path, base):
    """
    Checks to see if the provided file path is underneath the given base path.

    Args:
        path (str): The proposed extraction path of the tar file member to check.
        base (pathlib.Path): The path of the current working directory.

    Returns:
        bool: :py:data:`True` if the path is not under the proposed base path
        otherwise :py:data:`False`.
    """
    joint = base / path
    joint = joint.absolute().resolve()
    return not str(joint).startswith(str(base))


def badlink(info, base):
    """
    Checks to see if the provided link is underneath the given base path.

    Args:
        info (tarfile.TarInfo): The file member that is going to be extracted.
        base (pathlib.Path): The path of the current working directory.

    Returns:
        bool: :py:data:`True` if the path is not under the proposed base path
        otherwise :py:data:`False`.
    """
    link_path = base / Path(info.name).parent
    link_path = link_path.absolute().resolve()
    return badpath(info.linkname, link_path)


def get_safe_tarfile_members(tarfile):
    """
    Identify and return the members of a :py:class:`tarfile.TarFile` that are considered safe.
    See the documentation for :py:meth:`tarfile.TarFile.extractall` for more information.
    This function, as well as :py:func:`badlink` and :py:func:`badpath` were based on
    https://stackoverflow.com/a/10077309.

    Args:
        tarfile (tarfile.TarFile): The tar file to extract.

    Returns:
        list: A list of "safe" members to extract.
    """
    base = Path(".").resolve().absolute()

    result = []
    console = Console()
    for member in tarfile.getmembers():
        if badpath(member.name, base):
            console.print(f"[b red] {member.name} is blocked: illegal path")
        elif member.issym() and badlink(member, base):
            console.print(
                f"[b red] {member.name} is blocked: Symlink to [cyan]{member.linkname}"
            )
        elif member.islnk() and badlink(member, base):
            console.print(
                f"[b red] {member.name} is blocked: hard link to [cyan]{member.linkname}"
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
        def f_retry(*args, **kwargs):  # noqa: DOC109
            """
            The retry loop which attempts the function ``num_tries`` times
            and will catch exceptions passed into exceptions, then sleep
            for a random time uniformly sampled between 1 and
            base_delay*exp_factor**(attempt) seconds before retrying.

            Args:
                *args: Any arguments to the function.
                **kwargs: Any keyword arguments to the function.

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
