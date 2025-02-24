# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import sys
import importlib.util
from pathlib import Path
from importlib.metadata import version as importlib_version
from importlib.metadata import metadata

import sphinx_rtd_theme  # noqa: F401

from firewheel.control.repository_db import RepositoryDb
from firewheel.control.model_component_manager import ModelComponentManager
from firewheel.control.model_component_iterator import ModelComponentIterator

# -- Project information -----------------------------------------------------

project = "FIREWHEEL"
project_copyright = (
    "2024 National Technology & Engineering Solutions of Sandia, LLC (NTESS). "
    "Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains "
    "certain rights in this software"
)
author = "Sandia National Laboratories"

# The short X.Y version
version = importlib_version("firewheel")

# The full version, including alpha/beta/rc tags
release = importlib_version("firewheel")


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "sphinx.ext.autosummary",
    "sphinx.ext.graphviz",
    "sphinx.ext.inheritance_diagram",
    "myst_nb",
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
    "sphinx_copybutton",
    "sphinx_design",
]
# Spelling check needs an additional module that is not installed by default.
# Add it only if spelling check is requested so docs can be generated without it.
if "spelling" in sys.argv:
    extensions.append("sphinxcontrib.spelling")

# Spelling language.
spelling_lang = "en_US"
spelling_word_list_filename = ["spelling_wordlist.txt", "spelling_names.txt"]
spelling_exclude_patterns = [
    "**/dependencies.rst",
    "**/pip-dependencies.rst",
    "**/changelog.md",
]
spelling_show_suggestions = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["spelling_*.txt"]

source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "restructuredtext",
    ".md": "myst-nb",
    ".ipynb": "myst-nb",
}

numfig = True

# TODO FIXME
tls_verify = False

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Reference: https://rackerlabs.github.io/docs-rackspace/tools/rtd-tables.html
html_css_files = ["theme_overrides.css"]

# A shorter title for the navigation bar.  Default is the same as html_title.
html_short_title = "FIREWHEEL"

html_logo = "_static/logo.png"
html_favicon = "_static/favicon.ico"

# -- Options for linkcheck ---------------------------------------------------
linkcheck_anchors = False
linkcheck_ignore = [
    r"https://localhost:\d+/",
    r"http://localhost:\d+",
    r"https://linux.die.net/man/.*",
    r"https://dzone.com/.*",
]

# -- Extension configuration -------------------------------------------------
latex_elements = {
    "preamble": r"""
    \usepackage{pmboxdraw}
    \sphinxDUC{2529}{\pmboxdrawuni{2529}}
    \DeclareUnicodeCharacter{25CF}{$\bullet$}
    """,
}

# -- Options for myst-nb -------------------------------------------------

nb_execution_mode = "off"
suppress_warnings = ["mystnb.mime_priority"]

# -- Options for intersphinx extension ---------------------------------------

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    "python": (
        "https://docs.python.org/3/",
        (None, "local_inventories/python3_objects.inv"),
    ),
    "clustershell": (
        "https://clustershell.readthedocs.io/en/latest/",
        (None, "local_inventories/clustershell_objects.inv"),
    ),
    "netaddr": (
        "https://netaddr.readthedocs.io/en/latest/",
        (None, "local_inventories/netaddr_objects.inv"),
    ),
    "networkx": (
        "https://networkx.org/documentation/stable/",
        (None, "local_inventories/networkx_objects.inv"),
    ),
    "rich": (
        "https://rich.readthedocs.io/en/stable/",
        (None, "local_inventories/rich_objects.inv"),
    ),
}

# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Options for copybutton extension ----------------------------------------
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True

# -- Load all Model Components for documentation generation ------------------


class ModelComponentDocumentation:
    """
    This class enables identifying and loading all available model
    components.

    Once all components are loaded, it enables a user to create an
    index file with the MC documentation and then mock any necessary imports
    so that Sphinx autodoc will function as expected.

    To use this feature model components **MUST**:

    #. Be located within an installed FIREWHEEL repository.
    #. Have a file within the MC called either ``README.md`` or ``README.rst``.
    """

    def __init__(self, debug=False):
        """
        This class enables identifying and loading all available model
        components.

        Args:
            debug (bool): Whether or not to print deubgging output. Defaults to
                False.
        """
        self.repository_db = RepositoryDb()
        self.debug = debug

        # Greedily block against duplicate providers by choosing the first
        # provider for each attribute as default. It does not matter which
        # provider was intended as we only need to load (and not execute)
        # the model components.
        model_component_iter = ModelComponentIterator(
            self.repository_db.list_repositories()
        )

        attribute_defaults = {}
        # get all attributes provided:
        for mc_src in model_component_iter:
            _depends, provides, _precedes = mc_src.get_attributes()
            for provide in provides:
                if provide not in attribute_defaults:
                    attribute_defaults[provide] = mc_src.name

        self.mcm = ModelComponentManager(attribute_defaults_config=attribute_defaults)
        self.mock_import_set = set()

    def load_mcs(self, mc):
        """
        Load the given model component's plugin and model_component_objects files.

        Additionally, for each model component with a '.' in the name,
        Sphinx requires that we mock import all 'parent' packages e.g. for the
        ``dns.dns_objects`` MC, we need to mock import ``dns``.
        This function adds those mock imports to ``self.self.mock_import_set``.

        Args:
            mc (firewheel.control.model_component.ModelComponent): The MC to load.

        Raises:
            ImportError: If there is an issue loading the MC.
        """

        parent_name = mc.name
        while "." in parent_name:
            parent_name = parent_name[: parent_name.rfind(".")]
            if parent_name in self.mock_import_set:
                break
            self.mock_import_set.add(parent_name)

        # Load any model component objects, if they exist.
        try:
            unqualified_mc_objs_path = mc.get_model_component_objects_path()
            if unqualified_mc_objs_path != "":  # noqa: PLC1901
                mc_objs_path = Path(mc.path) / unqualified_mc_objs_path
                if self.debug:
                    print(f"trying mc_objs_path: {mc_objs_path}")
                try:
                    # pylint: disable=protected-access
                    self.mcm._import_model_component_objects(
                        mc_objs_path.absolute(), mc.name
                    )
                except ImportError as exc:
                    if "already been imported" in str(exc):
                        pass
                    else:
                        print(
                            f"Import error graph object for model component {mc.name} {exc}"
                        )
        except RuntimeError as exc:
            print(
                f"Unable to get graph objects path for model component {mc.name} {exc}."
            )

        # Load the plugin, if it exists.
        try:
            unqualified_plugin_path = mc.get_plugin_path()
            if self.debug:
                print(
                    f"Checking plugin objects for model component {mc.name} at path "
                    f'"{unqualified_plugin_path}"'
                )
            if unqualified_plugin_path != "":  # noqa: PLC1901
                loaded = False

                plugin_path = Path(mc.path) / unqualified_plugin_path
                try:
                    if self.debug:
                        print(f"trying plugin_path : {plugin_path}")

                    spec = importlib.util.spec_from_file_location(
                        f"{mc.name}_plugin", plugin_path.absolute()
                    )
                    if spec is None:
                        raise ImportError("Plugin file not found.")
                    try:
                        module = importlib.util.module_from_spec(spec)
                    except Exception as exp:
                        raise ImportError(exp) from exp
                    try:
                        spec.loader.exec_module(module)
                        # necessary line not in the mcm function
                        if f"{mc.name}_plugin" not in sys.modules:
                            sys.modules[f"{mc.name}_plugin"] = module
                        loaded = True
                    except FileNotFoundError as exp:
                        raise ImportError(
                            "Specified plugin file not found: %s" % (exp,)
                        ) from exp

                except ImportError as exp:
                    raise ImportError(f"{mc.name} plugin import error: {exp}") from exp
                if not loaded:
                    raise ImportError(f"{mc.name} plugin not loaded.")
        except RuntimeError:
            print("Unable to get plugin path for model component %s." % (mc.name,))

    def get_mc_list(self):
        """Get the list of all loaded model components and then load them."""

        model_component_iter = ModelComponentIterator(
            self.repository_db.list_repositories()
        )

        for mc_src in model_component_iter:
            self.mcm.build_dependency_graph([mc_src], install_mcs=False)
            for mc in self.mcm.get_ordered_model_component_list():
                self.load_mcs(mc)

    def make_index(self, basepath):
        """
        Automatically generate an index file which contains all the current model components.

        Additionally, this function will symlink the README files to the directory of
        the index file so that Sphinx will correctly read them.
        This function overwrites the existing ``model_components/index.rst`` file.

        Args:
            basepath (pathlib.Path): The path for adding the index file.
        """
        # Get the list of model components
        index = """.. _available_model_components:

#############################
Model Component Documentation
#############################

"""

        # First remove all existing symlinks
        all_files = [basepath / f for f in basepath.iterdir()]
        for f in all_files:
            if f.is_symlink():
                f.unlink()

        for repo in self.repository_db.list_repositories():
            model_component_iter = ModelComponentIterator(iter([repo]))

            # Get the repository README (if it exists)
            readme_path = None
            repo_path = Path(repo["path"])
            if (repo_path / "README.rst").exists():
                readme_path = repo_path / "README.rst"
            elif (repo_path / "README.md").exists():
                readme_path = repo_path / "README.md"

            if readme_path:
                with readme_path.open("r") as fhand:
                    index += f"\n{fhand.read()}"
            else:
                # Check if there is package metadata
                repo_name = repo_path.name
                try:
                    message = metadata(f"{repo_name}")
                    source = message.get_payload()
                    if source:
                        index += f"\n{source}"
                except importlib.metadata.PackageNotFoundError:
                    index += f"""
{'*' * len(repo_name)}
{repo_name}
{'*' * len(repo_name)}
"""

            index += """

.. toctree::
    :maxdepth: 1

"""

            for mc in sorted(model_component_iter, key=lambda mc: mc.name):
                # Get path to doc dir
                mc_path = Path(mc.path)
                if (mc_path / "README.rst").exists():
                    readme_path = mc_path / "README.rst"
                elif (mc_path / "README.md").exists():
                    readme_path = mc_path / "README.md"
                else:
                    continue

                print(f"README PATH={readme_path}")
                self.sym_link_directories(
                    readme_path, basepath / f"{mc.name}{readme_path.suffix}"
                )
                index += f"    {mc.name}\n"

            index += "\n"

        with (basepath / "index.rst").open("w") as index_file:
            index_file.write(index)

    def sym_link_directories(self, curr, new):
        """
        Symlink the README from the model component directory to the new directory.

        Args:
            curr (str): The current path for the MC.
            new (str): The new path for the MC.
        """
        if new.exists():
            new.unlink()
        new.symlink_to(curr)


# Check to see if we should include model component documentation
path = Path("model_components")
if path.exists():
    # Load all model components into the path
    mcd = ModelComponentDocumentation()
    mcd.get_mc_list()

    # Build out the new model components TOCTREE
    mcd.make_index(path)
    autodoc_mock_imports = list(mcd.mock_import_set)
