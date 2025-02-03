
import pytest
from pathlib import Path

from firewheel.control.repository_db import RepositoryDb


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


@pytest.fixture
def repository_db_test_path():
    return Path("/tmp/fw_repo_test.json")


class TestRepositoryDb:
    """Test the ``RepositoryDb`` object."""

    @staticmethod
    def _entry_matches_repo_dict(repo_entry, repo_dict):
        path = repo_entry["path"]
        return path == repo_dict["path"]

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
        repo_dict = list(repository_db.list_repositories()).pop()
        assert len(repo_dict) == 1
        assert self._entry_matches_repo_dict(repo_entry, repo_dict)

        location.unlink(missing_ok=True)
        assert location.exists() is False

    def test_add_repository(self, repository_db, repo_entry):
        repository_db.add_repository(repo_entry)
        repo_dict = list(repository_db.list_repositories()).pop()
        assert len(repo_dict) == 1
        assert self._entry_matches_repo_dict(repo_entry, repo_dict)

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
    def test_add_repository_invalid(self, invalid_entry, exception, repository_db):
        with pytest.raises(exception):
            repository_db.add_repository(invalid_entry)

    def test_duplicate_repository(self, repository_db, repo_entry):
        repository_db.add_repository(repo_entry)
        repository_db.add_repository(repo_entry)
        repo_dict = list(repository_db.list_repositories()).pop()
        assert len(repo_dict) == 1
        assert self._entry_matches_repo_dict(repo_entry, repo_dict)

    def test_delete_repository(self, repository_db, repo_entry):
        repository_db.add_repository(repo_entry)
        assert repository_db.delete_repository(repo_entry) == 1

    def test_list_repositories(self, repository_db, repo_entries):
        orig_entry_count = len(list(repository_db.list_repositories()))
        for entry in repo_entries:
            repository_db.add_repository(entry)
        repo_list = list(repository_db.list_repositories())
        assert len(repo_list) == orig_entry_count + len(repo_entries)
