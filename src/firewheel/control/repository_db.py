import os
import json
from pathlib import Path

from importlib_metadata import entry_points

from firewheel.config import config
from firewheel.lib.log import Log


class RepositoryDb:
    """
    Provides an interface to the Repository database.
    This database is functionally a JSON file which stores a list of locally installed
    model component repositories which are uniquely identified by their path.

    A repository, as stored in the database, is expected to have the form:

    .. code-block:: json

        {
            "path": ""
        }

    """

    def __init__(
        self,
        db_basepath=config["system"]["default_output_dir"],
        db_filename="repositories.json",
    ):
        """
        Set up the instance variables and path to the RepositoryDB file.

        Args:
            db_basepath (str): The base path where the RepositoryDB file is stored.
            db_filename (str): The name of the RepositoryDB file. Defaults to "repositories.json".
        """
        self.log = Log(name="RepositoryDb").log
        self.db_file = Path(db_basepath) / Path(db_filename)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_file.exists():
            with self.db_file.open("w") as db:
                json.dump([], db)

    def list_repositories(self):
        """
        List the repositories in the database.

        This method will list all repositories in the database and check for
        any installed Python packages that provide the ``firewheel.mc_repo``
        `entry point <https://setuptools.pypa.io/en/latest/userguide/entry_point.html>`_.

        Returns:
            list: An iterator, where each dictionary is a repository.
                (See repository format for the database).
        """
        entries = []

        # Add all local model component repositories
        if self.db_file.exists():
            with self.db_file.open("r") as db:
                try:
                    local_entries = json.load(db)
                    entries.extend(local_entries)
                except json.decoder.JSONDecodeError:
                    self.log.warning("Repository DB unable to be read.")

        # Add all model components that have been added via entry points
        for entry in entry_points(group="firewheel.mc_repo"):
            entries.append({"path": entry.load()[0]})

        return iter(entries)

    def add_repository(self, repository):
        """
        Add a new repository entry to the database.

        Args:
            repository (dict): A repository dictionary to add. See format for the database.

        Returns:
            int: Number of entries added, 0 for duplicate repository or 1 for a single repository.
        """
        self._validate_repository(repository)

        # Get all local model component repositories
        if self.db_file.exists():
            with self.db_file.open("r") as db:
                try:
                    entries = json.load(db)
                except json.decoder.JSONDecodeError:
                    self.log.warning("Repository DB unable to be read.")
                    entries = []
        else:
            # No database file exists yet.
            entries = []

        if any(entry["path"] == repository["path"] for entry in entries):
            self.log.debug("Ignoring duplicate repository: %s", repository)
            return 0

        entries.append(repository)
        with self.db_file.open("w") as db:
            json.dump(entries, db)

        self.log.debug("Added repository: %s", repository)
        return 1

    def delete_repository(self, repository):
        """
        Delete a repository entry from the database.

        Args:
            repository (dict): A repository dictionary to delete.

        Returns:
            int: Number of entries removed (expect 0 or 1), or None if an
            error occurred.
        """
        # Get all local model component repositories
        if self.db_file.exists():
            with self.db_file.open("r") as db:
                try:
                    entries = json.load(db)
                except json.decoder.JSONDecodeError:
                    self.log.warning("Repository DB unable to be read.")
                    entries = []
        else:
            # No database file exists yet.
            entries = []

        try:
            entries.remove(repository)
            self._validate_repository(repository)
            self.log.debug("Removed repository: %s", repository)
        except ValueError:
            self.log.debug(
                "%s repository did not exist and could not be removed.", repository
            )
            return 0
        except FileNotFoundError:
            self.log.debug(
                "%s repository path does not exist, but was removed anyways.",
                repository,
            )

        with self.db_file.open("w") as db:
            json.dump(entries, db)

        return 1

    def _validate_repository(self, repository):
        """
        Validate a given repository has the correct format

        Args:
            repository (dict): A repository dictionary to add. See format for the database.

        Raises:
            KeyError: if there is a missing key/val pair in the repository.
            FileNotFoundError: If the repository does not exist.
            PermissionError: If the user is unable to access that directory.
        """

        # Validate repository format.
        if "path" not in repository:
            raise KeyError('Cannot add malformed repository to database. Need "path".')
        expected_key_len = 1
        if len(repository.keys()) != expected_key_len:
            raise KeyError(
                "Cannot add malformed repository to database."
                f" Expected {expected_key_len} key."
            )

        # Check if the path exists
        path = os.path.abspath(repository["path"])
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Path '{path}' does not exist! Please create it before adding it as a repository."
            )

        if not os.access(path, os.R_OK):
            raise PermissionError(
                f"Do not have correct permissions to access '{path}'!"
            )
