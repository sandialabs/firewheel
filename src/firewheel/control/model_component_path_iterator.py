from typing import Set, Iterator
from pathlib import Path

from firewheel.lib.log import Log


class ModelComponentPathIterator:
    """
    This class takes in a repository iterator and enables searching
    over all the repositories for model components and their specific
    fully qualified paths.
    """

    def __init__(self, repositories) -> None:
        """
        Create an iterator to find model components among a set of MC repos.

        Args:
            repositories (list_iterator): The list of repositories.
        """
        self.log = Log(name="ModelComponentPathIterator").log
        self._mc_paths: Set[Path] = set()
        for repo in repositories:
            repo_mc_paths = self.walk_repository_for_model_component_paths(repo["path"])
            self._mc_paths.update(repo_mc_paths)

    def walk_repository_for_model_component_paths(self, path: str) -> Iterator[Path]:
        """
        Search each repository for model component paths.

        Args:
            path (str): Path of the repository.

        Returns:
            Iterator[Path]: An iterator providing paths to all model
                components contained within the repository.
        """
        repo_path = Path(path)
        if not repo_path.exists():
            self.log.warning(
                "Unable to locate repository at expected location: %s", repo_path
            )
            return iter(())
        return self._recurse_repository(repo_path)

    def _recurse_repository(self, path: Path) -> Iterator[Path]:
        """
        Recursively search directories for model components.

        This is a helper method for the ``walk_repository_for_model_component_paths()``
        method. It will walk the path tree to create set of directories within
        the repository which are model components.

        Args:
            path (pathlib.Path): Path of the repository.

        Yields:
            Path: An absolute path to the next model component
                found by the iterator.
        """
        if self._is_path_model_component(path):
            yield path.absolute()
        else:
            for subdirectory in filter(lambda path: path.is_dir(), path.iterdir()):
                yield from self._recurse_repository(subdirectory)

    def _is_path_model_component(self, path: Path) -> bool:
        """
        Check to see if the passed-in directory is a model component. The condition for being
        a model component in this context is if a ``MANIFEST`` file exists.

        Args:
            path (pathlib.Path): Path of the potential model component.

        Returns:
            bool: py:data:`True` if a MANIFEST file exists within the
                directory, :py:data:`False` otherwise.
        """
        return any(entry.name == "MANIFEST" for entry in path.iterdir())

    def __iter__(self):
        return self

    def __next__(self) -> str:
        try:
            return str(self._mc_paths.pop())
        except KeyError:
            raise StopIteration from None
