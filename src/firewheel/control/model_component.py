import os
import enum
import pprint
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from itertools import chain

import yaml
from rich.live import Live
from rich.console import Group
from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn,
    TimeElapsedColumn,
    MofNCompleteColumn,
)

from firewheel.lib.log import Log
from firewheel.lib.utilities import hash_file
from firewheel.control.image_store import ImageStore
from firewheel.control.repository_db import RepositoryDb
from firewheel.control.model_component_install import ModelComponentInstall
from firewheel.control.model_component_exceptions import (
    MissingImageError,
    MissingVmResourceError,
)
from firewheel.control.model_component_path_iterator import ModelComponentPathIterator
from firewheel.vm_resource_manager.vm_resource_store import VmResourceStore


class _ModelComponentFile(ABC):
    """An abstract base class representing a generic (cacheable) file object."""

    def __init__(self, path, file_store):
        """
        Instantiate the object representing a binary file.

        Args:
            path (pathlib.Path): The path to the binary file.
            file_store (firewheel.lib.minimega.file_store.FileStore): A
                file store object that will serve as the destination for
                the file.

        Notes:
            This class is similar to the :py:class:`lib.minimega.file_store.FileStoreFile`
            but represents a file at a different point in its lifetime. Where that
            object provides an interface to an object that should already be present
            in a file store, this object provides an interface for a file specified
            in a model component that may or may not have already been uploaded to
            a file store. These two interfaces may ultimately be merged.
        """
        self.path = path
        self.file_store = file_store
        self.file_store_status = None
        self._verify_existence()

    @property
    def name(self):
        return self.path.name

    @property
    def size(self):
        # Size of the file in bytes
        return self.path.stat().st_size

    @property
    def modification_timestamp(self):
        return datetime.utcfromtimestamp(self.path.stat().st_mtime)

    @property
    def requires_upload(self):
        self.update_file_store_status()
        return self.file_store_status in (
            _FileStoreStatus.MISSING,
            _FileStoreStatus.OUTDATED,
        )

    def _verify_existence(self):
        if not self.path.exists():
            self._handle_missing_file()

    @abstractmethod
    def _handle_missing_file(self):
        raise NotImplementedError

    def _determine_file_store_status(self):
        # Exit immediately if the file appears to be missing
        if (store_timestamp := self.file_store.get_file_upload_date(self.name)) is None:
            return _FileStoreStatus.MISSING
        # The file exists in the store; compare the two files
        if store_timestamp == self.modification_timestamp:
            # Exceedingly unlikely that two different files have identical timestamps;
            # exit quickly without checking hashes
            return _FileStoreStatus.CURRENT
        # Hash files as a comparison
        # (typically faster than assuming outdated and triggering a reupload)
        store_hash = self.file_store.get_file_hash(self.name)
        binary_hash = hash_file(self.path)
        if store_hash and store_hash == binary_hash:
            return _FileStoreStatus.CURRENT
        if store_timestamp < self.modification_timestamp:
            return _FileStoreStatus.OUTDATED
        warnings.warn(
            f"Cached file `{self.name}` appears to be out-of-sync with "
            f"the MC-provided copy (`{self.path}`) ",
            stacklevel=2,
        )
        return _FileStoreStatus.UNKNOWN

    def update_file_store_status(self):
        """Update the binary's status based on its availability in the file store."""
        self.file_store_status = self._determine_file_store_status()

    def upload(self):
        """Upload the binary file to the file store."""
        self.file_store.add_file(self.path)


class _Image(_ModelComponentFile):
    """A binary file object representing a VM image."""

    def _handle_missing_file(self):
        # The image does not exist. This is a problem... unless the image is already
        # in the file store then it may or may not be an issue. Either way, it is
        # weird and the user should fix it.
        raise MissingImageError(
            f"The image {self.path} is not present in the model component."
        )

    def upload(self):
        """Upload the binary file to the file store."""
        self.file_store.add_image_file(self.path)


class _VMResource(_ModelComponentFile):
    """A binary file object representing a VM resource."""

    def _handle_missing_file(self):
        raise MissingVmResourceError(self.path)


class _FileStoreStatus(enum.Enum):
    """An enumeration of file statuses that may be assigned to files in a file store."""

    CURRENT = enum.auto()
    OUTDATED = enum.auto()
    MISSING = enum.auto()
    UNKNOWN = enum.auto()


class ModelComponent:
    """
    This class defines a Model Component which is the building block
    for FIREWHEEL experiments.
    """

    # Default databases and file stores are common to all model components
    # and have nontrivial instantiation times (only instantiate them once)
    _default_repository_db = RepositoryDb()
    _default_vm_resource_store = VmResourceStore()
    _default_image_store = ImageStore()

    def __init__(
        self,
        name=None,
        path=None,
        repository_db=None,
        arguments=None,
        vm_resource_store=None,
        image_store=None,
        install=None,
    ):
        """
        Constructor. Allows specification of various database objects, typically
        used for testing. **Must specify either name or path.**
        **If both are specified, name must match the MANIFEST at path.**

        Args:
            name (str): The name of this ModelComponent. Corresponds
                to the "name" property of the MANIFEST.
            path (str): The path to this ModelComponent, specifically
                the directory containing the MANIFEST file.
            repository_db (RepositoryDb): A RepositoryDb object. If not
                given, will use the default RepositoryDb constructor.
            arguments (dict): A dictionary with a 'plugin' key. The
                value of this key is itself a dictionary, with a format
                specified by ``ModelComponentManager``. Keyword
                arguments use key/value pairs in the dict. Positional
                arguments use the empty string (``''``) as a key, and
                may be a single value or a list of values.
            vm_resource_store (firewheel.vm_resource_manager.vm_resource_store.VmResourceStore):
                A ``VmResourceStore`` object. If not given, will use the
                default ``VmResourceStore`` constructor.
            image_store (firewheel.control.image_store.ImageStore): An
                ``ImageStore`` object. If not given, will use the default
                ``ImageStore`` constructor.
            install (bool): Whether or not to install the model
                component. If :py:data:`True`, the MC will be installed
                automatically, and if :py:data:`False`, the MC will not
                be installed. If left as :py:data:`None`, the user will
                be prompted about whether or not the MC should be
                installed via the ``INSTALL`` script.

        Raises:
            ValueError: Caused if a user didn't specify name or path.
            ValueError: Caused if the name and manifest name do not match.
            ValueError: Caused if the arguments dictionary is malformed.
        """
        self.name = name
        self.path = path
        self._install = install

        self.repository_db = repository_db or self._default_repository_db
        self.vm_resource_store = vm_resource_store or self._default_vm_resource_store
        self.image_store = image_store or self._default_image_store

        if self.name is None and self.path is None:
            raise ValueError("Must specify at least name or path.")

        if self.path is None:
            self._resolve_path()
        else:
            # Resolve path ends up loading the manifest (it must anyway).
            # No need to duplicate the work.
            self.manifest = self._load_manifest(self.path)

        if self.name is None:
            self.name = self.manifest["name"]
        elif self.name != self.manifest["name"]:
            raise ValueError("Specified name and manifest name do not match.")

        self.dep_id = None

        if arguments is None:
            self.arguments = {"plugin": {}}
        else:
            if (
                not isinstance(arguments, dict)
                or "plugin" not in arguments
                or not isinstance(arguments["plugin"], dict)
            ):
                raise ValueError(
                    "Malformed arguments dictionary. Must contain a"
                    + "plugin key with a dictionary value."
                )
            self.arguments = arguments
        self.log = Log(name="ModelComponent").log

        # Set progress bars for this MC
        self.overall_cache_progress = Progress(
            MofNCompleteColumn(),
            SpinnerColumn(spinner_name="line"),
            TextColumn(
                "[yellow]Populating/refreshing large files in the cache for MC "
                f"`[white]{self.name}`[/white]. This may take a while..."
            ),
        )
        self.large_file_cache_progress = Progress(
            TimeElapsedColumn(),
            TextColumn("[yellow]- {task.description}"),
        )
        self.cache_progress_group = Group(
            self.overall_cache_progress, self.large_file_cache_progress
        )

    def _load_manifest(self, path):
        """
        Try to get the path to the ModelComponents `MANIFEST` file.

        Args:
            path (str): The path from where to load the ``MANIFEST`` file.

        Returns:
            string: The full path to the `MANIFEST` file.

        Raises:
            RuntimeError: If the `MANIFEST` file does not exist or if the `MANIFEST` is
                malformed (i.e. not valid JSON).
        """
        if not path or not os.path.exists(path):
            raise RuntimeError("Unable to locate model component at expected location.")

        manifest_name = os.path.join(path, "MANIFEST")

        try:
            with open(manifest_name, "r", encoding="utf8") as fopened:
                return yaml.safe_load(fopened)
        except yaml.YAMLError as exp:
            raise RuntimeError(
                f"Malformed MANIFEST in model component at path {path}"
            ) from exp

    def __hash__(self):
        return self.path.__hash__()

    def _resolve_path(self):
        """
        Try to find the path for the current model component by iterating
        through all model components searching for the one whose name matches.
        Once a match is found the manifest and path attributes are set.

        Raises:
            ValueError: If it cannot find the model component.
        """
        path_iter = ModelComponentPathIterator(self.repository_db.list_repositories())

        for path in path_iter:
            manifest = self._load_manifest(path)
            if self.name == manifest["name"]:
                self.path = path
                self.manifest = manifest
                if self._install is None or self._install is True:
                    mci = ModelComponentInstall(self)
                    # Note that ``bool(None)`` evaluates to ``False``
                    mci.run_install_script(insecure=bool(self._install))
                return

        raise ValueError(f"Unable to locate model component with name '{self.name}'.")

    def __eq__(self, other):
        """
        Determine if two model components are the same. Equality is based
        on having the same name and the same path. This function also
        verifies that itself and another are not None as that would cause
        issues.

        Args:
            other (ModelComponent): The other model component.

        Returns:
            bool: True if they are the same, False otherwise.
        """
        # Catch Nones. Can't use comparison because it could recurse.
        if type(self) != type(other):  # noqa: E721
            return False
        if self.name != other.name:
            return False
        if self.path != other.path:
            return False
        # Same path implies same manifest
        return True

    def __ne__(self, other):
        """
        Determine if two model components not equal. In this case
        we are using the inverse of `__eq__`.

        Args:
            other (ModelComponent): The other model component.

        Returns:
            bool: True if they are not the same, False otherwise.
        """
        return not self == other

    def __str__(self):
        """
        Provide a nicely formatted string describing the ModelComponent. The string
        provides a pretty-printed MANIFEST, the path, and the Dependency Graph ID.

        Returns:
            str: A nicely formatted string describing the ModelComponent
        """
        return str(
            f"{pprint.pformat(self.manifest)}\n"
            f"Path: {self.path!s}\n"
            f"Dependency Graph ID: {self.dep_id!s}"
        )

    def get_attribute_depends(self):
        """
        Get the attributes depends block from the manifest.

        Returns:
            list: Contains the attributes depends list or an empty list if there
            are no depends attributes.
        """
        if "attributes" not in self.manifest or not self.manifest["attributes"]:
            return []
        if "depends" not in self.manifest["attributes"]:
            return []

        return self.manifest["attributes"]["depends"]

    def get_attribute_provides(self):
        """
        Get the attributes provides block from the manifest.

        Returns:
            list: Contains the attributes provides list or an empty list if there
            are no provides attributes.
        """
        if "attributes" not in self.manifest or not self.manifest["attributes"]:
            return []
        if "provides" not in self.manifest["attributes"]:
            return []

        return self.manifest["attributes"]["provides"]

    def get_attribute_precedes(self):
        """
        Get the attributes precedes block from the manifest.

        Returns:
            list: Contains the attributes precedes list or an empty list if there
            are no preceded attributes.
        """
        if "attributes" not in self.manifest or not self.manifest["attributes"]:
            return []
        if "precedes" not in self.manifest["attributes"]:
            return []

        return self.manifest["attributes"]["precedes"]

    def get_attributes(self):
        """
        Get the attributes block from the manifest.

        Returns:
            tuple: Contains both the attributes depends, provides and precedes lists.
        """
        return (
            self.get_attribute_depends(),
            self.get_attribute_provides(),
            self.get_attribute_precedes(),
        )

    def get_model_component_precedes(self):
        """
        Get the model component's precedes list.

        Returns:
            list: The model components preceded model components.
        """
        if "precedes" not in self.manifest["model_components"]:
            return []

        return self.manifest["model_components"]["precedes"]

    def get_model_component_depends(self):
        """
        Get the model component's dependency list.

        Returns:
            list: The model components dependencies.
        """
        if "depends" not in self.manifest["model_components"]:
            return []

        return self.manifest["model_components"]["depends"]

    def upload_files(self):
        """
        Upload any VM Resources and Images needed for the experiment to the cache.
        """
        threshold = 250_000_000  # 25 MB
        vm_resources = self._collect_vm_resources()
        images = self._collect_images()
        # Upload small files silently
        small_vmr_uploads = [
            vmr for vmr in vm_resources if vmr.requires_upload and vmr.size <= threshold
        ]
        self._upload_small_files(small_vmr_uploads)
        # Use progress displays for large file uploads
        large_vmr_uploads = [
            vmr for vmr in vm_resources if vmr.requires_upload and vmr.size > threshold
        ]
        image_uploads = [image for image in images if image.requires_upload]
        if large_file_uploads := large_vmr_uploads + image_uploads:
            self._upload_large_files(large_file_uploads)

    def _upload_small_files(self, files):
        for file in files:
            file.upload()

    def _upload_large_files(self, files):
        with Live(self.cache_progress_group):
            overall_task_id = self.overall_cache_progress.add_task("", total=len(files))
            for file in files:
                self._upload_large_file(file)
                self.overall_cache_progress.update(overall_task_id, advance=1)

    def _upload_large_file(self, file):
        # Upload a large file to the cache, including progress displays
        is_outdated = file.file_store_status == _FileStoreStatus.OUTDATED
        action = "Updating" if is_outdated else "Adding"
        update_cache_task_id = self.large_file_cache_progress.add_task(
            description=f"{action} file: `{file.name}`"
        )
        file.upload()
        self.large_file_cache_progress.stop_task(update_cache_task_id)

    def _collect_vm_resources(self):
        """
        Collect all VM resources from the manifest.

        Returns:
            list: A list of VM resource objects determined from the manifest.

        Raises:
            RuntimeError: If the ``vm_resources`` field in the MANIFEST is not a list.
        """
        vm_resource_list = self.manifest.get("vm_resources", [])

        if not isinstance(vm_resource_list, list):
            # The `vm_resources` must be in a list
            raise RuntimeError(
                "Malformed MANIFEST, the `vm_resources` attribute must be a list. "
                f"It is currently: `{vm_resource_list}` of type "
                f"`{type(vm_resource_list)}`."
            )

        vm_resource_names = chain.from_iterable(
            self._interpret_manifest_vmr_specification(manifest_vm_resource)
            for manifest_vm_resource in vm_resource_list
        )
        return [
            _VMResource(Path(self.path, vmr_name), self.vm_resource_store)
            for vmr_name in vm_resource_names
        ]

    def _interpret_manifest_vmr_specification(self, manifest_vm_resource):
        """
        Interpret a specified VM resource string provided in a manifest file.

        Args:
            manifest_vm_resource (str): A string specifyin a VM resource, VM
                resource directory, or collection of VM resources according to
                a pattern.

        Notes:
            This method interprets the path of the VM resources in the following way:

            * Non-recursively upload all directory files: ``path_to_dir``,
              ``path_to_dir/``, or ``path_to_dir/*`` (all equivalent)
            * Non-recursively upload all directory files matching a pattern: ``path_to_dir/*.ext``
            * Recursively upload all files: ``path_to_dir/**``, ``path_to_dir/**/``, or
              ``path_to_dir/**/*`` (all equivalent)
            * Recursively upload all files matching a pattern: ``path_to_dir/**/*.ext``
        """
        if Path(self.path).joinpath(manifest_vm_resource).is_dir():
            manifest_vm_resource += "/*"

        # replace all ** not already followed by **/* with **/*
        manifest_vm_resource = manifest_vm_resource.replace("**/*", "**")
        manifest_vm_resource = manifest_vm_resource.replace("**", "**/*")
        if "*" in manifest_vm_resource:
            enumerated_resources = [
                str(p.relative_to(self.path))
                for p in Path(self.path).glob(manifest_vm_resource)
                if p.is_file()
            ]
        else:
            enumerated_resources = [manifest_vm_resource]
        return enumerated_resources

    def _collect_images(self):
        """
        Collect all images from the manifest.

        Returns:
            list: A list of image objects determined from the manifest.
        """
        architecture_image_data = self.manifest.get("images", {})
        image_relative_paths = chain.from_iterable(
            info.get("paths", []) for info in architecture_image_data
        )
        return [
            _Image(Path(self.path, image_path), self.image_store)
            for image_path in image_relative_paths
        ]

    def set_dependency_graph_id(self, new_id):
        """
        Set the dependency graph ID.

        Args:
            new_id (int): The ID that will become the dependency graph ID.
        """
        self.dep_id = new_id

    def get_dependency_graph_id(self):
        """
        Get the dependency graph ID.

        Returns:
            int: The dependency graph ID.
        """
        return self.dep_id

    def get_plugin_path(self):
        """
        Try to get the path to the ModelComponents `plugin` file.

        Returns:
            string: The full path to the `plugin` file or an empty string if an error
            occurred.

        Raises:
            RuntimeError: If the `plugin` does not exist or is a valid path but not
                a file.
        """
        try:
            plugin_path = os.path.join(self.path, self.manifest["plugin"])
            if not os.path.exists(plugin_path):
                raise RuntimeError(
                    f"Plugin file ({plugin_path}) for ModelComponent {self.name} does "
                    "not exist."
                )
            if not os.path.isfile(plugin_path):
                raise RuntimeError(
                    f"Plugin file ({plugin_path}) for ModelComponent {self.name} is a "
                    "valid path but not a file."
                )
            return self.manifest["plugin"]
        except KeyError:
            return ""

    def get_model_component_objects_path(self):
        """
        Try to get the path to the ModelComponents `model_components_objects` file.

        Returns:
            string: The full path to the `model_component_objects` file or an
            empty string if an error occurred.

        Raises:
            RuntimeError: If the `model_component_objects` file does not exist
                or is a valid path but not a file.
        """
        try:
            mc_objs_path = Path(self.path) / self.manifest["model_component_objects"]
            if not mc_objs_path.exists():
                raise RuntimeError(
                    f"Model component objects file ({mc_objs_path}) for "
                    f"ModelComponent {self.name} does not exist."
                )
            if not mc_objs_path.is_file():
                raise RuntimeError(
                    f"Model component objects file ({mc_objs_path}) "
                    f"for ModelComponent {self.name} is a valid path but not a file."
                )
            return self.manifest["model_component_objects"]
        except KeyError:
            return ""
