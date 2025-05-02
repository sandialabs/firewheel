
import os
from unittest.mock import patch

import pytest
from pathlib import Path

from firewheel.control.repository_db import RepositoryDb


@pytest.fixture
def mock_permissioned_filesystem():
    # Save a reference to the original `os.access` method before mocking
    os_access = os.access

    def _deny_user_access_to_root_home_directory(path, mode, **kwargs):
        return False if Path(path) == Path("/root") else os_access(path, mode, **kwargs)

    with patch("os.access", side_effect=_deny_user_access_to_root_home_directory):
        yield


def create_test_repo(repo_path):
    repo_path.mkdir()
    return str(repo_path)


@pytest.fixture
def repo_entry(tmp_path):
    return {"path": create_test_repo(tmp_path / "test_repo")}


@pytest.fixture
def repo_entries(tmp_path):
    return [{"path": create_test_repo(tmp_path / f"test_repo_{_}")} for _ in range(2)]


@pytest.fixture
def repository_db():
    repository_db = RepositoryDb(
        db_filename="test_repositories.json",
    )
    yield repository_db
    # Ensure all repositories are removed during teardown
    for repo in repository_db.list_repositories():
        repository_db.delete_repository(repo)


@pytest.fixture
def repository_db_test_path():
    return Path("/tmp/fw_repo_test.json")


class TestRepositoryDb:
    """Test the ``RepositoryDb`` object."""

    @staticmethod
    def _entry_in_repo_list(repo_entry, repo_list):
        path = repo_entry["path"]
        return any(entry["path"] == path for entry in repo_list)

    def test_new_repository(self, repository_db_test_path):
        location = repository_db_test_path
        if location.exists():
            location.unlink(missing_ok=True)

        assert location.exists() is False

        repository_db = RepositoryDb(
            db_basepath=location.parent,
            db_filename=location.name
        )
        assert location.exists() is True
        location.unlink(missing_ok=True)

        assert location.exists() is False

    def test_corrupt_repository_add(self, repository_db_test_path, repo_entry):
        location = repository_db_test_path

        with location.open("w") as f:
            f.write("invalid json")

        repository_db = RepositoryDb(
            db_basepath=location.parent,
            db_filename=location.name
        )
        assert location.exists() is True

        repository_db.add_repository(repo_entry)
        repo_list = list(repository_db.list_repositories())
        assert self._entry_in_repo_list(repo_entry, repo_list)

        location.unlink(missing_ok=True)
        assert location.exists() is False

    def test_add_repository(self, repository_db, repo_entry):
        assert repository_db.add_repository(repo_entry) == 1
        repo_list = list(repository_db.list_repositories())
        assert self._entry_in_repo_list(repo_entry, repo_list)

    @pytest.mark.parametrize(
        ["invalid_entry", "exception"],
        [
            # Test invalid directory structures
            [
                {
                    "path": "/tmp/test-invalid",  # nosec
                    "invalid": "value",
                },
                KeyError,
            ],  # ----------------------------------------- too many keys
            [{"invalid": "value"}, KeyError],  # ---------- wrong key
            [{"path": "/root"}, PermissionError],  # ------ bad permissions
            [{"path": "asdf"}, FileNotFoundError],  # ----- missing directory
        ],
    )
    def test_add_repository_invalid(
        self, invalid_entry, exception, mock_permissioned_filesystem, repository_db
    ):
        with pytest.raises(exception):
            repository_db.add_repository(invalid_entry)

    def test_duplicate_repository(self, repository_db, repo_entry):
        orig_entry_count = len(list(repository_db.list_repositories()))
        assert repository_db.add_repository(repo_entry) == 1
        assert repository_db.add_repository(repo_entry) == 0
        repo_list = list(repository_db.list_repositories())
        assert self._entry_in_repo_list(repo_entry, repo_list)
        # The entry should only be added once
        assert len(repo_list) == orig_entry_count + 1

    def test_delete_repository(self, repository_db, repo_entry):
        repository_db.add_repository(repo_entry)
        assert repository_db.delete_repository(repo_entry) == 1

    def test_list_repositories(self, repository_db, repo_entries):
        orig_entry_count = len(list(repository_db.list_repositories()))
        for entry in repo_entries:
            repository_db.add_repository(entry)
        curr_count = len(list(repository_db.list_repositories()))
        assert curr_count == orig_entry_count + len(repo_entries)
