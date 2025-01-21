import os
import pprint
from pathlib import Path
from datetime import datetime

import yaml
import rich
from rich.progress import Progress, TextColumn, SpinnerColumn, TimeElapsedColumn

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


class ModelComponent:
    """
    This class defines a Model Component which is the building block
    for FIREWHEEL experiments.
    """
    default_image_cache_progress = Progress(
        TextColumn("[yellow]{task.description} This may take a while."),
        SpinnerColumn(spinner_name="line"),
        TimeElapsedColumn(),
    )

    def __init__(
        self,
        name=None,
        path=None,
        repository_db=None,
        arguments=None,
        vm_resource_store=None,
        image_store=None,
        install=None,
        image_cache_progress=None,
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
            image_cache_progress (rich.progress.Progress): The progress stlye
                to use when displaying image related cache operations. If left
                unset, the default progress bar style (defined by the
                ``default_image_cache_progress`` attribute) will be used.

        Raises:
            ValueError: Caused if a user didn't specify name or path.
            ValueError: Caused if the name and manifest name do not match.
            ValueError: Caused if the arguments dictionary is malformed.
        """
        self.name = name
        self.path = path
        self._install = install
        self._image_cache_progress = (
            image_cache_progress or self.default_image_cache_progress
        )

        if repository_db is not None:
            self.repository_db = repository_db
        if vm_resource_store is not None:
            self.vm_resource_store = vm_resource_store
        if image_store is not None:
            self.image_store = image_store

        if self.name is None and self.path is None:
            raise ValueError("Must specify at least name or path.")

        if self.path is None:
            self._resolve_path()

            if self._install is None or self._install is True:
                installer = ModelComponentInstall(self, console=None)
                force_install = bool(self._install)  # `None` is falsy
                installer.run_install_script(insecure=force_install)

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

    @property
    def repository_db(self):
        """
        Use the specified :class:`RepositoryDb`.

        Returns:
            RepositoryDb: The specified repository database.
        """
        try:
            if self._repository_db is None:
                # pylint: disable=attribute-defined-outside-init
                self._repository_db = RepositoryDb()
        except AttributeError:
            # pylint: disable=attribute-defined-outside-init
            self._repository_db = RepositoryDb()
        return self._repository_db

    @repository_db.setter
    def repository_db(self, value):
        # pylint: disable=attribute-defined-outside-init
        self._repository_db = value

    @property
    def vm_resource_store(self):
        """
        Use the specified :class:`VmResourceStore`.

        Returns:
            VmResourceStore: The specified resource store.
        """
        try:
            if self._vm_resource_store is None:
                # pylint: disable=attribute-defined-outside-init
                self._vm_resource_store = VmResourceStore()
        except AttributeError:
            # pylint: disable=attribute-defined-outside-init
            self._vm_resource_store = VmResourceStore()
        return self._vm_resource_store

    @vm_resource_store.setter
    def vm_resource_store(self, value):
        # pylint: disable=attribute-defined-outside-init
        self._vm_resource_store = value

    @property
    def image_store(self):
        """
        Use the specified :class:`ImageStore`.

        Returns:
            ImageStore: The specified :class:`ImageStore`.
        """
        try:
            if self._image_store is None:
                # pylint: disable=attribute-defined-outside-init
                self._image_store = ImageStore()
        except AttributeError:
            # pylint: disable=attribute-defined-outside-init
            self._image_store = ImageStore()
        return self._image_store

    @image_store.setter
    def image_store(self, value):
        # pylint: disable=attribute-defined-outside-init
        self._image_store = value

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
        self._upload_vm_resources()
        self._upload_images()

    def _upload_vm_resource(self, resource):
        """
        Upload a file to the VmResourceStore.
        It interrupts the path of the VM resources in the following way:

        * Non-recursive all dir's files: `path_to_dir`,
          `path_to_dir/`, or `path_to_dir/*`
        * Non-recursive all dir's files matching pattern: `path_to_dir/*.ext`
        * Recursive all files: `path_to_dir/**`, `path_to_dir/**/`, or `path_to_dir/**/*`
        * Recursive  all files matching pattern: `path_to_dir/**/*.ext`

        Raises:
            MissingVmResourceError: if the given file path does not exist,
                or its modification time cannot be determined.

        Args:
            resource (str): Path relative to this component's root to the file being
                            uploaded.

        Returns:
            str: Indication of what happened. This may be one of:
                `no_date` -- There was no upload date for the given file in the
                            VmResourceStore. It was uploaded.
                `new_hash` -- The modified time of the file on disk differs from the
                            last upload time in the VmResourceStore and the hashes did not match.
                            File was uploaded.
                `same_hash` -- The file on disk was modified after the upload time in
                            the VmResourceStore but the hashes are the same. File was
                            not uploaded.
                `False` -- None of the other conditions occurred. For example, the file
                        on disk was modified before the VmResourceStore upload time
        """
        path = os.path.join(self.path, resource)
        try:
            modified_time = os.path.getmtime(path)
            last_modified_date = datetime.utcfromtimestamp(modified_time)
            self.log.debug(
                "Resource %s in %s has modified time of %s",
                resource,
                self.manifest["name"],
                last_modified_date,
            )
        except OSError as exp:
            raise MissingVmResourceError(path) from exp

        upload_date = self.vm_resource_store.get_file_upload_date(
            os.path.basename(resource)
        )
        self.log.debug("VM Resource store file has upload date of %s", upload_date)

        if upload_date is None:
            self.log.debug(
                "Resource %s not found in store. Uploading.", os.path.basename(resource)
            )
            self.vm_resource_store.add_file(path)
            return "no_date"

        if last_modified_date != upload_date:
            self.log.debug("Resource on disk is different from store. Checksuming.")
            resource_hash = hash_file(path)
            store_hash = self.vm_resource_store.get_file_hash(resource)
            self.log.debug(
                "Resource %s//%s on disk has hash %s and in store has %s",
                self.manifest["name"],
                resource,
                resource_hash,
                store_hash,
            )

            if resource_hash != store_hash:
                self.log.debug("Newer resource checksum differs. Uploading.")
                self.vm_resource_store.add_file(path)
                return "new_hash"
            return "same_hash"
        return False

    def _upload_vm_resources(self):
        """
        Upload all VM resources from the manifest. It interrupts the path
        of the VM resources in the following way:

        * Non-recursive all dir's files: `path_to_dir`,
          `path_to_dir/`, or `path_to_dir/*`
        * Non-recursive all dir's files matching pattern: `path_to_dir/*.ext`
        * Recursive all files: `path_to_dir/**`, `path_to_dir/**/`, or `path_to_dir/**/*`
        * Recursive  all files matching pattern: `path_to_dir/**/*.ext`

        Returns:
            bool: True if any resource was uploaded, False otherwise.

        Raises:
            RuntimeError: If the `vm_resources` field in the MANIFEST is not a list.
        """
        if "vm_resources" not in self.manifest:
            return False

        if not isinstance(self.manifest["vm_resources"], list):
            # The vm_resources must be in a list
            raise RuntimeError(
                'Malformed MANIFEST, the "vm_resources" attribute '
                f'must be a list. It is currently: "{self.manifest["vm_resources"]}"'
                f'of type "{type(self.manifest["vm_resources"])}"'
            )

        any_uploaded = False

        # Interpret path as follows:
        # Non-recursive, all dir's files, non-recursive: path_to_dir, path_to_dir/ -> path_to_dir/*
        # Non-recursive, all dir's files matching pattern path_to_dir/*.ext -> no change
        # Recursive - all files: path_to_dir/**, path_to_dir/**/ -> path_to_dir/**/*
        # Recursive - all files matching pattern: path_to_dir/**/*.ext -> no change
        for manifest_vm_resource in self.manifest["vm_resources"]:
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
            for resource in enumerated_resources:
                self.log.debug(
                    "Uploading resource %s from model component %s",
                    resource,
                    self.manifest["name"],
                )
                result = self._upload_vm_resource(resource)
                if result == "same_hash":
                    result = False
                any_uploaded = any_uploaded or bool(result)
        return any_uploaded

    def _upload_images(self):
        """
        Upload all image files from the manifest.

        Raises:
            MissingImageError: If the image is not found in the model component.

        Returns:
            list: Actions for each specified file. Order is sequential,
            proceeding through images, for each image proceed through each
            specified file before moving to next image. Possible actions are:

            * `no_date` -- There was no upload date for the given file in the
                           ImageStore. It was uploaded.
            * `new_hash` -- The modified time of the file on disk differs from the
                            last upload time in the ImageStore and the hashes did not match.
                            File was uploaded.
            * `same_hash` -- The file on disk was modified after the upload time in
                            the ImageStore but the hashes are the same. File was
                            not uploaded.
            * `False` -- None of the other conditions occurred. For example, the file
                        on disk was modified before the ImageStore upload time
        """
        if "images" not in self.manifest:
            return False
        images = self.manifest["images"]
        ret_val = []
        for image in images:
            for end_path in image["paths"]:
                path = os.path.join(self.path, end_path)
                try:
                    modified_time = os.path.getmtime(path)
                    last_modified_date = datetime.utcfromtimestamp(modified_time)
                except OSError as exp:
                    # The image does not exist. This is a problem...unless the
                    # image is already in the file store then it may or may not be an
                    # issue. Either way it is weird and the user should fix it.
                    raise MissingImageError(
                        f"The image {path} is not present in the model component."
                    ) from exp

                # Check the upload date of the image in the FileStore. If the image
                # does not exist, None will be returned.
                if not self.image_store.check_path(os.path.basename(path)):
                    upload_date = None
                else:
                    upload_date = self.image_store.get_file_upload_date(
                        os.path.basename(path)
                    )

                # If the image does not exist in the FileStore, then add it.
                # If it does exist, then compare times. If the last modified
                # time of the disk image is greater than the uploaded time of
                # the image in the FileStore, then we should check the MD5 sums. If the
                # MD5 sums differ, than we need to re-upload the image.
                if upload_date is None:
                    self._update_image_cache(f"Adding {end_path} to cache.", path)
                    ret_val.append("no_date")
                elif last_modified_date != upload_date:
                    # If date is different then hash it
                    disk_hash = hash_file(path)
                    store_hash = self.image_store.get_file_hash(os.path.basename(path))
                    # If hashes differ upload new image
                    if disk_hash != store_hash:
                        self._update_image_cache(f"Updating {end_path} in cache.", path)
                        ret_val.append("new_hash")
                    else:
                        ret_val.append("same_hash")
                else:
                    ret_val.append(False)

        return ret_val

    def _use_live_image_cache_progress(method):
        # Use a live progress bar if it exists already
        def _inner(self, *args, **kwargs):
            try:
                with self._image_cache_progress:
                    return method(self, *args, **kwargs)
            except rich.errors.LiveError:
                return method(self, *args, **kwargs)

        return _inner

    @_use_live_image_cache_progress
    def _update_image_cache(self, task_description, path):
        task = self._image_cache_progress.add_task(description=task_description)
        self.image_store.add_image_file(path)
        self._image_cache_progress.stop_task(task)

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
