from __future__ import annotations

import os
import time
import shutil
import tarfile
from io import BufferedReader
from lzma import LZMADecompressor
from types import TracebackType
from typing import Dict, List, Tuple, Union, Optional, Generator
from logging import Logger
from datetime import datetime
from contextlib import contextmanager

from minimega import Error as MinimegaError  # type: ignore[import-untyped]

from firewheel.config import config
from firewheel.lib.log import Log
from firewheel.lib.utilities import hash_file, get_safe_tarfile_members
from firewheel.lib.minimega.api import minimegaAPI


class FileStoreFile:
    """
    A pseudo-File-like object representing a file stored in the FileStore.

    It is pseudo-File-like because it is a Context Manager (it is used with the
    "with" statement) and it provides a read() method. It does not implement
    other portions of the File interface.
    """

    def __init__(self, filename: str, database: FileStore):
        """
        Create a new instance of FileStoreFile.

        Args:
            filename (str): Name of the file in the database to access
            database (FileStore): Instance of FileStore where the file is stored
        """
        self.filename = filename
        self.database = database
        self.handle: Union[BufferedReader, None] = None

        self.log = Log(name="FileStoreFile").log

    def __enter__(self) -> FileStoreFile:
        """
        Open (for reading) a specific file in the FileStore.

        Returns:
            FileStoreFile: Reference to this instance.
        """
        file_location = self.database.get_path(self.filename)
        # pylint: disable=consider-using-with
        self.handle = open(file_location, "rb")
        return self

    def read(self, size: int = 16 * 1024 * 1024) -> bytes:
        """
        Read the next chunk of data from a file handle.
        Assumes __enter__ has been called (call this from within a "with" block.

        Args:
            size (int): The size of the chunk to read from the file.
                    Default is 16 MiB.

        Returns:
            A chunk of data of the specified size (default 16 MiB) from the file
            referenced by handle.

        Raises:
            RuntimeError: If the file handle is not found.
        """
        if not self.handle:
            self.log.error("File handle not found.")
            raise RuntimeError(
                "File handle not found. Are you using 'with' or calling '__enter__()'?"
            )

        return self.handle.read(size)

    def __exit__(  # noqa: DOC109, DOC110
        self,
        exc_type: Union[BaseException, None] = None,
        exc_val: Union[BaseException, None] = None,
        exc_tb: Union[TracebackType, None] = None,
    ) -> bool:
        """
        Close the file.

        Args:
            exc_type: Any exception type. Ignored.
            exc_val: Any exception value. Ignored.
            exc_tb: The exception trace back. Ignored.

        Returns:
            bool: Whether the file was successfully closed. Will be False if it
            was never opened in the first place.
        """
        if self.handle:
            self.handle.close()
            return True
        self.log.warning("Handle for file does not exist, can't close")
        return False


class FileStore:
    """
    A repository for files uses a distributed file system for easy
    access on all hosts in a FIREWHEEL cluster. Currently uses minimega to store
    files. Ideally, this should be modifiable without affecting the interface.
    """

    def __init__(
        self,
        store: str,
        mm_base: str = config["minimega"]["base_dir"],
        decompress: bool = False,
        log: Optional[Logger] = None,
    ) -> None:
        """
        Initializes the object with a minimegaAPI connection.

        Args:
            store (str): The relative path from the minimega files directory for this FileStore.
            mm_base (str): The root directory for minimega.
            decompress (bool): Whether to decompress files by default when using this FileStore.
            log (firewheel.lib.log.Log.log): Override the default FIREWHEEL log.

        Raises:
            PermissionError: If the FileStore was unable to create the cache due to
                bad permissions.
        """

        self.store = store
        self.decompress = decompress

        if log is None:
            self.log = Log(name="FileStore").log
        else:
            self.log = log

        self.mm_api = minimegaAPI(mm_base=mm_base)

        self.cache_base = config["minimega"]["files_dir"]
        self.cache = os.path.join(self.cache_base, self.store)
        try:
            # Don't worry about conditions where the cache directory already
            # exists.
            if not os.path.isdir(self.cache):
                os.makedirs(self.cache, exist_ok=True)
        except PermissionError as exp:
            self.log.exception(
                "FileStore unable to initialize: permission "
                "denied trying to create cache directory."
            )
            raise exp

    def _get_lock(self, cache_location: str) -> bool:
        """
        Get a lock (FIREWHEEL-specific, not OS lock) for a specific location in
        the local cache.

        Args:
            cache_location (str): The name of the file to lock.

        Returns:
            bool: True on lock released.
        """
        self.log.debug("Acquiring lock for %s", cache_location)
        os.mkdir(cache_location + "-lock")
        return True

    def _wait_for_lock(self, cache_location: str) -> None:
        """
        Wait for the (FIREWHEEL-specific) lock on a specific location in the
        local cache.

        Args:
            cache_location (str): The name of the file to wait for the lock on.
        """
        sleep_interval = 0.25
        count = 0
        while os.path.exists(cache_location + "-lock"):
            # Only print the message once every 5 seconds
            if count % 20 == 0:
                self.log.debug(
                    "Waiting for lock on: %s",
                    cache_location,
                )
            time.sleep(sleep_interval)
            count += 1

            # If we have been waiting for more than 5 min an error might have occurred
            # We should warn the user once every 5 seconds.
            if count >= 1200 and count % 20 == 0:
                self.log.warning(
                    "Have been waiting for lock for %s for more than five minutes. "
                    "It is possible that an error occurred causing an issue with releasing "
                    "the lock. You may want to consider either restarting the experiment "
                    "or using ``firewheel mm flush_locks <cache>``. NOTE that using "
                    "``mm flush_locks`` could have unintended side effects.",
                    cache_location,
                )

    def _release_lock(self, cache_location: str) -> bool:
        """
        Release the (FIREWHEEL-specific) lock on a specific location in the
        local cache.

        Args:
            cache_location (str): The name of the file to release the lock on.

        Returns:
            bool: True on lock released.
        """
        self.log.debug("Releasing lock for %s", cache_location)
        try:
            os.rmdir(cache_location + "-lock")
            return True
        except FileNotFoundError as exp:
            self.log.exception(exp)

        return False

    @contextmanager
    def file_lock(self, location: str) -> Generator[Optional[bool], None, None]:
        """
        Context Manager for acquiring locks. Enables using the with context
        to get a lock using an optional timeout. Release lock at the end of
        the with block.

        Args:
            location (str): Location of the file to lock.

        Yields:
            Optional[bool]: :py:data:`True` on lock acquired.
        """
        try:
            # Try to acquire the lock.
            lock_acquired = self._get_lock(location)
        except OSError as exp:
            self.log.exception(exp)
            lock_acquired = None
        try:
            yield lock_acquired
        finally:
            if lock_acquired:
                # If we were able acquire the lock, we should release it now.
                self._release_lock(location)

    def _strip_extension(self, filename: str) -> str:
        """
        Check to see if a filename has a compression extension and remove it
        if it does.
        Currently checking for ``{".xz". ".tar.gz", ".tar", ".tgz"}``.

        Args:
            filename (str): The name of the file to update (if needed).

        Returns:
            str: The updated filename without the extension
        """

        if filename.endswith(".xz"):
            filename = filename.rstrip(".xz")
        elif filename.endswith(".tar.gz"):
            filename = filename.replace(".tar.gz", "")
        elif filename.endswith(".tar"):
            filename = filename.rstrip(".tar")
        elif filename.endswith(".tgz"):
            filename = filename.rstrip(".tgz")

        return filename

    def _decompress_error(
        self, exp: OSError, tmp_local_path: str, host_file_path: str
    ) -> None:
        """
        Output specific warnings/errors if an issue happened while trying to decompress a file.
        Additionally, try to remove the file which caused the issue.

        Args:
            exp (OSError): The exception being raised.
            tmp_local_path (str): The temporary path of the file name used for
                decompression.
            host_file_path (str): The location to cache the file locally.

        """
        self.log.error("Unable to decompress file: %s: %s", tmp_local_path, exp)
        for f_name in [tmp_local_path, host_file_path]:
            self.log.debug("Attempting to remove file=%s", f_name)
            try:
                os.remove(f_name)
            except FileNotFoundError:
                self.log.debug("File was already removed.")

    def _minimega_get_data(
        self, host_file_path: str, filename: str, decompress: bool = False
    ) -> Tuple[str, str]:
        """
        Get the requested file from minimega and return the path to the locally
        cached version of the file.
        Detect if the file is already cached and just return the path.

        Args:
            host_file_path (str): The location to cache the file locally.
            filename (str): The name of the file to get from minimega.
            decompress (bool): Whether to decompress the file.

        Returns:
            tuple: Contains the path to the locally cached file and an empty string. If
            there is an error then it returns empty string and the second argument
            is a string description of the error.
        """
        if not os.path.exists(host_file_path):
            # Get a lock for downloading the file
            try:
                with self.file_lock(host_file_path):
                    # we have the lock, so we will get the file
                    if decompress and filename.endswith(".xz"):
                        tmp_local_path = f"{host_file_path}.xz"
                        success = self._minimega_get_file(tmp_local_path, filename)

                        # Decompress the xz file
                        decompressor = LZMADecompressor()
                        try:
                            with open(tmp_local_path, "rb") as xz_file:
                                with open(host_file_path, "wb") as cache_file:
                                    chunk = 1024 * 1024 * 512
                                    cache_file.write(
                                        decompressor.decompress(xz_file.read(chunk))
                                    )
                                    while not decompressor.eof:
                                        cache_file.write(
                                            decompressor.decompress(xz_file.read(chunk))
                                        )
                        except OSError as exp:
                            self._decompress_error(exp, tmp_local_path, host_file_path)
                            return "", "decompress"

                    elif decompress and any(
                        map(filename.endswith, {".tar.gz", ".tar", ".tgz"})
                    ):
                        tmp_local_path = f"{host_file_path}.tgz"
                        success = self._minimega_get_file(tmp_local_path, filename)

                        # Decompress the file
                        try:
                            with tarfile.open(tmp_local_path, "r") as tar_file:
                                # The checking for this happens in "get_safe_tarfile_members"
                                tar_file.extractall(  # noqa: S202
                                    os.path.dirname(host_file_path),
                                    members=get_safe_tarfile_members(tar_file),
                                )
                        except OSError as exp:
                            self._decompress_error(exp, tmp_local_path, host_file_path)
                            return "", "decompress"
                    else:
                        success = self._minimega_get_file(host_file_path, filename)

                    if success:
                        return host_file_path, ""

                    os.remove(host_file_path)
                    return "", "failed"
            except TimeoutError as exp:
                self.log.exception(exp)
                self.log.debug("Waiting for someone else to download the file")
                self._wait_for_lock(host_file_path)
                return host_file_path, ""

        # Check for a file downloading lock; if it exists, loop until
        # it doesn't
        self._wait_for_lock(host_file_path)
        return host_file_path, ""

    def get_file(self, filename: str) -> FileStoreFile:
        """
        Get an FileStoreFile instance representing a specific file.

        Importantly, this method returns successfully even if the specified file
        does not exist. In this case, a FileNotFoundError is raised upon using
        the returned FileStoreFile.

        Use example::

            with file_store.get_file('my_vm_resource.py') as vm_resource_file:
                chunk = vm_resource_file.read()

            Invalid file example:
            # Raises FileNotFoundError
            with file_store.get_file('invalid') as vm_resource_file:
                pass

        Args:
            filename (str): The name of the file to get a representation for.

        Returns:
            FileStoreFile: An instance of FileStoreFile for the requested file.
        """
        return FileStoreFile(filename, self)

    def get_file_path(self, filename: str) -> str:
        """
        Get the proper path to the given file.

        Args:
            filename (str): The name of the file for which to find the path.

        Returns:
            str: The fully qualified path of the file.
        """
        decompress = self.decompress
        mm_file_path = os.path.join(self.store, filename)
        if decompress:
            mm_file_path = self._strip_extension(mm_file_path)
        host_file_path = os.path.join(config["minimega"]["files_dir"], mm_file_path)
        return host_file_path

    def check_path(self, filename: str) -> bool:
        """
        Check to see if a file's path exists.

        Args:
            filename (str): The name of the file to cache.

        Returns:
            bool: True if it exists, False otherwise.
        """
        return os.path.exists(self.get_file_path(filename))

    def get_path(self, filename: str) -> str:
        """
        Ensure a specified file is cached locally.

        Args:
            filename (str): The name of the file to cache.

        Returns:
            str: The path to the locally cached file.

        Raises:
            FileNotFoundError: When the local path for the image cannot be found.
            RuntimeError: When the file could not be decompressed.
        """
        host_file_path = self.get_file_path(filename)

        local_path, error = self._minimega_get_data(
            host_file_path, filename, self.decompress
        )

        if error == "failed":
            self.log.error("Unable to get the path for: %s", filename)
            raise FileNotFoundError(f"Unable to get the local path for: {filename}")
        if error == "decompress":
            self.log.error("Unable to decompress file: %s", filename)
            raise RuntimeError(f"Unable to decompress {filename}")

        if self.decompress:
            local_path = self._strip_extension(local_path)
        return local_path

    def get_file_size(self, filename: str) -> int:
        """
        Returns the length (in bytes) of a file in the FileStore.
        This method ignores the local cache.

        Args:
            filename (str): Name of the file.

        Returns:
            int: Size of the file, measured in bytes.

        Raises:
            FileNotFoundError: If the file is not found in the database.
            RuntimeError: If the number of files does not equal one.
        """
        basename = os.path.basename(filename)
        file_list = self.list_contents(basename)
        try:
            mm_file = file_list[0]
        except IndexError as exp:
            raise FileNotFoundError(exp) from exp
        if len(file_list) != 1:
            raise RuntimeError("Number of files does not equal 1.")
        file_size = mm_file[2]
        return int(file_size)

    def _minimega_get_file(self, cache_location: str, filename: str) -> bool:
        """
        Perform the mechanics of a read operation from minimega.
        This function assumes that you have the file's lock already.

        Args:
            cache_location (str): The local file to write to.
            filename (str): The minimega file to read.

        Returns:
            bool: True on success, False otherwise (or an Exception is raised).

        Raises:
            FileNotFoundError: If the file is not found.
            MinimegaError: If there is an error running minimega.
            Error: If there is an error running minimega. This is an alias for MinimegaError.
        """

        if not os.path.exists(cache_location):
            self.log.debug("Getting file: %s", filename)
            mm_file_path = os.path.relpath(
                cache_location, config["minimega"]["files_dir"]
            )
            try:
                self.mm_api.mm.file_get(mm_file_path)
            except MinimegaError as exp:
                self.log.exception(exp)
                if (
                    "no such file" in str(exp).lower()
                    or "file not found" in str(exp).lower()
                ):
                    raise FileNotFoundError(exp) from exp
                if "already in flight" in str(exp).lower():
                    pass
                else:
                    self.log.error(
                        "exception getting %s from %s at %s with cache_location=%s",
                        filename,
                        self.store,
                        mm_file_path,
                        cache_location,
                    )
                    raise MinimegaError from exp  # noqa: DOC501
            sleep_interval = 0.25
            file_transferring = True
            while file_transferring:
                ret = self.mm_api.mm.file_status()
                local_ret = ret[0]["Tabular"]
                file_transferring = False
                for local_file_status in local_ret:
                    if local_file_status[0] == mm_file_path:
                        file_transferring = True
                        break
                time.sleep(sleep_interval)

        self.log.debug("Finished writing to file")

        # Now that we've downloaded the file, check if it has a backing file.
        # If it does, download it.
        # Note: This only works for QCOW2 files.
        try:
            raw_disk_info = self.mm_api.mm.disk_info(cache_location)
        except MinimegaError as exp:
            self.log.exception(exp)
            if (
                "no such file" in str(exp).lower()
                or "file not found" in str(exp).lower()
            ):
                raise FileNotFoundError(exp) from exp
            self.log.error(
                "exception getting disk info from cache_location=%s",
                cache_location,
            )
            raise MinimegaError from exp
        mapped_disk_info = self.mm_api.mmr_map(raw_disk_info, first_value_only=True)
        backing_file = mapped_disk_info["backingfile"]
        if backing_file:
            # get the relative path from the store.
            self.log.debug('Downloading backing file: "%s".', backing_file)
            backing_file_rel_path = os.path.relpath(backing_file, self.cache)
            self.get_path(backing_file_rel_path)

        return True

    def get_file_hash(self, filename: str) -> str:
        """
        Returns the hash of a file in the MM files directory

        Args:
            filename (str): Name of the file.

        Returns:
            str: Hash of the file.
        """
        basename = os.path.basename(filename)
        host_file_path = os.path.join(
            config["minimega"]["files_dir"], self.store, basename
        )
        if os.path.exists(host_file_path):
            return hash_file(host_file_path)
        return ""

    def get_file_upload_date(self, filename: str) -> Optional[datetime]:
        """
        Returns the upload date of a file in minimega

        Args:
            filename (str): Name of the file.

        Returns:
            datetime.datetime: Datetime date that the file was uploaded into local the
            minimega files directory.
        """
        basename = os.path.basename(filename)
        host_file_path = os.path.join(
            config["minimega"]["files_dir"], self.store, basename
        )
        self.log.debug(
            "in get_file_upload date with filename=%s and host_file_path=%s",
            basename,
            host_file_path,
        )
        try:
            upload_time = os.path.getmtime(host_file_path)
            last_upload_date = datetime.utcfromtimestamp(upload_time)
            self.log.debug(
                "basename %s  has upload time of %s", basename, last_upload_date
            )
            return last_upload_date
        except OSError:
            self.log.debug("Filename %s has not been uploaded", filename)
            return None

    def list_contents(self, pattern: str = "") -> List[Tuple[str, str, str]]:
        """
        List the contents of the FileStore.

        Args:
            pattern (str): pattern to match filenames against

        Returns:
            list: A list of dictionaries, where each dictionary is an entry from the
            FileStore.

        Raises:
            RuntimeError: If there is an error getting the minimega file list.
            Exception: If an error occurred during this method.
        """
        try:
            if pattern:
                search_arg = f"{self.store}/{pattern}"
            else:
                search_arg = self.store
            mm_resp = self.mm_api.mm.file_list(search_arg)
            if len(mm_resp) != 1 or "Tabular" not in mm_resp[0]:
                raise RuntimeError("Error getting the minimega file list.")
            mm_files = mm_resp[0]["Tabular"]
            mm_file_list = [
                (e[0], os.path.relpath(e[1], self.store), e[2]) for e in mm_files
            ]
            return mm_file_list
        except Exception as exp:
            self.log.error("Exception getting running file_list on %s", self.store)
            raise exp

    def list_distinct_contents(self, pattern: str = "") -> List[str]:
        """
        List the contents of the FileStore.

        Args:
            pattern (str): The pattern to match filenames against.

        Returns:
            list: A list of dictionaries, where each dictionary is an entry from the FileStore.

        Raises:
            Exception: If there is an error getting the file list.
        """
        try:
            mm_files = self.list_contents(pattern=pattern)
            mm_filenames = [e[1] for e in mm_files]
            return mm_filenames
        except Exception as exp:
            self.log.error("Exception getting running file_list on %s", self.store)
            raise exp

    def add_image_file(self, path: str, force: bool = True) -> bool:
        """
        Adds an image file to FileStore.

        Args:
            path (str): The path of the file being transferred.
            force (bool): Whether to force adding the new image.

        Returns:
            bool: Whether the broadcast was successful; i.e. Whether each host in the mesh
            has a consistent version of the file in their cache.
        """
        # first add_file for the compressed image
        self.add_file(path, force=force)
        # next get_path which will force decompression
        _source_dir, filename = os.path.split(path)
        basename = os.path.basename(filename)
        cached_path = os.path.join(self.cache, basename)
        self.log.debug(
            "in add_image_file with path=%s, cached_path=%s", path, cached_path
        )

        expected_basename = self._strip_extension(basename)
        if expected_basename != basename and force:
            self.remove_file(expected_basename)

        local_path = self.get_path(cached_path)
        self.log.debug("in add_image_file with local_path=%s", local_path)
        mm_file_path = os.path.relpath(local_path, config["minimega"]["files_dir"])
        ret = self.broadcast_get_file(mm_file_path)
        self.log.debug("in add_image_file with ret=%s", ret)
        return ret

    def _check_mesh_file_consistency(
        self, mm_file_path: str
    ) -> Dict[str, Union[List[Dict[str, Optional[Union[str, List[str]]]]], bool]]:
        """
        Checks whether there is a consistent version of the file on all hosts in the mesh.

        Args:
            mm_file_path (str): The path of the file being transferred.

        Returns:
            dict: Dictionary containing information such as `consistent`
            (if all versions of the file are the same),
            `exists` (whether any host has a version of this a file).
        """
        mesh_size = self.mm_api.get_mesh_size()
        local_response = self.mm_api.mm.file_list(mm_file_path)
        mesh_responses = self.mm_api.mm.mesh_send("all", f"file list {mm_file_path}")
        ret = {"local_response": local_response, "mesh_responses": mesh_responses}
        consistent = True
        if len(mesh_responses) + 1 != mesh_size:
            consistent = False
        else:
            for mesh_response in mesh_responses:
                if mesh_response["Tabular"] or local_response[0]["Tabular"]:
                    if mesh_response["Tabular"] != local_response[0]["Tabular"]:
                        consistent = False
        ret["consistent"] = consistent
        ret["exists"] = len(local_response[0]["Tabular"]) > 0
        return ret

    def _check_mesh_transfer(self, mm_file_path: str) -> bool:
        """
        Blocks until a final transfer is complete.

        Args:
            mm_file_path (str): The path of the file being transferred.

        Returns:
            bool: Whether each host in the mesh has a consistent version of the file in their cache.
        """
        sleep_interval = 0.25
        file_transferring = True
        while file_transferring:
            time.sleep(sleep_interval)
            ret = self.mm_api.mm.mesh_send("all", "file status")
            mapped_ret = self.mm_api.mmr_map(ret)
            file_transferring = False
            for host_resp in mapped_ret.values():
                for transferring_file in host_resp:
                    if transferring_file["filename"] == mm_file_path:
                        file_transferring = True
                        break
                if file_transferring:
                    break
            self.log.debug("file_transferring=%s", file_transferring)
            if file_transferring:
                continue

            consistency_response = self._check_mesh_file_consistency(mm_file_path)
            consistent = consistency_response["consistent"]
            exists = consistency_response["exists"]
            self.log.debug("consistent=%s, exists=%s", consistent, exists)
            if consistent and exists:
                return True
            file_transferring = False
        return False

    def broadcast_get_file(self, mm_file_path: str) -> bool:
        """
        Add a file to the FileStore and ensure that all hosts download it into their cache.

        Args:
            mm_file_path (str): The path of the file to be uploaded into the FileStore.

        Returns:
            bool: Whether the broadcast was successful; i.e. Whether each host in the mesh
            has a consistent version of the file in their cache.

        Raises:
            Exception: If an error occurs interacting with minimega.
        """
        if self.mm_api.get_mesh_size() == 1:
            return True

        max_attempts = 10
        for i in range(max_attempts):
            try:
                self.mm_api.mm.mesh_send("all", f"file get {mm_file_path}")
            except Exception as exp:
                self.log.debug(
                    "broadcast_get_file: attempt=%s, file=%s, exception=%s",
                    i,
                    mm_file_path,
                    exp,
                )
                time.sleep(0.5)
                if "already in flight" in str(exp).lower():
                    break

                raise exp

        transfer_response = self._check_mesh_transfer(mm_file_path)
        self.log.debug("transfer_response=%s", transfer_response)
        return transfer_response

    def add_file_from_content(
        self, content: str, filename: str, force: bool = True, broadcast: bool = True
    ) -> None:
        """
        Creates file and add it to the FileStore with the given filename.

        Args:
            content (str): Content of the file to add.
            filename (str): The name of the file to be uploaded into the FileStore.
            force (bool): Whether to attempt to remove the file from the FileStore
                first.
            broadcast (bool): Whether to have all mesh nodes attempt to put this file
                in their cache.
        """
        if force:
            try:
                self.remove_file(filename)
            except OSError as exp:
                self.log.debug(
                    "Exception running remove_file %s on %s when trying to add_file",
                    filename,
                    self.store,
                )
                self.log.exception(exp)

        mm_file_path = os.path.join(self.store, filename)
        host_file_path = os.path.join(config["minimega"]["files_dir"], mm_file_path)
        try:
            with open(host_file_path, "w", encoding="utf8") as f_name:
                f_name.write(content)
        except OSError as exp:
            self.log.error("Adding %s to %s at %s", filename, self.store, mm_file_path)
            self.log.exception(exp)
        if broadcast:
            self.broadcast_get_file(mm_file_path)

    def add_file(self, path: str, force: bool = True) -> None:
        """
        Add a file to the FileStore.

        Args:
            path (str): The path of the file to be uploaded into the FileStore.
            force (bool): If True, then remove the existing file before adding
                the new one.

        Raises:
            OSError: If there is an issue adding the file.
        """
        source_dir, filename = os.path.split(path)
        basename = os.path.basename(filename)
        self.log.info(
            "in add_file with source_dir=%s and filename=%s, basename=%s, from path=%s",
            source_dir,
            filename,
            basename,
            path,
        )
        if force:
            try:
                self.remove_file(filename)
            except OSError as exp:
                self.log.error(
                    "Running remove_file %s on %s when trying to add_file",
                    filename,
                    self.store,
                )
                self.log.exception(exp)

        mm_file_path = os.path.join(self.store, basename)
        host_file_path = os.path.join(config["minimega"]["files_dir"], mm_file_path)
        try:
            shutil.copy2(path, host_file_path)
        except OSError as exp:
            self.log.error("Adding %s to %s at %s", filename, self.store, mm_file_path)
            self.log.exception(exp)
            raise exp
        try:
            self.mm_api.mm.mesh_send("all", f"file get {mm_file_path}")
        # pylint: disable=broad-except
        except Exception as exp:
            self.log.error("Adding %s to %s at %s", filename, self.store, mm_file_path)
            self.log.exception(exp)
            raise OSError from exp

    def remove_file(self, filename: str) -> None:
        """
        Do the removal of a file name from minimega.

        Args:
            filename (str): minimega file name to remove.

        Raises:
            OSError: If an error occurs interacting with minimega.
        """
        mm_file_path = os.path.join(self.store, filename)
        try:
            self.mm_api.mm.file_delete(mm_file_path)
            self.mm_api.mm.mesh_send("all", f"file delete {mm_file_path}")
            self._check_mesh_file_consistency(mm_file_path)
            # need to assert we get correct response here
        except Exception as exp:
            msg = f"Removing {filename} to {self.store} at {mm_file_path}"
            self.log.error(msg)
            self.log.exception(exp)
            raise OSError(msg) from exp
