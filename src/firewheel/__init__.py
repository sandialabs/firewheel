from pathlib import Path
from importlib.metadata import version

__version__ = version("firewheel")

FIREWHEEL_PACKAGE_DIR = Path(__file__).parent
