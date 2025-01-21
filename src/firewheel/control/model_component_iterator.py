from firewheel.control.model_component import ModelComponent
from firewheel.control.model_component_path_iterator import ModelComponentPathIterator


class ModelComponentIterator:
    """
    This class iterates over the various repositories looking for model components.
    """

    def __init__(self, repositories, console=None):
        """
        Initialize the path iterator.

        Args:
            repositories (list_iterator): The list of repositories.
            console (rich.console.Console): A console to use for displaying
                model component information to the user.
        """
        self.path_iter = ModelComponentPathIterator(repositories)
        self._mc_console = console

    def __iter__(self):
        return self

    def __next__(self):
        return ModelComponent(path=next(self.path_iter), console=self._mc_console)
