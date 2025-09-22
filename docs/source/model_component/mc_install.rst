.. _mc_install:

############################
Model Component INSTALL file
############################

Some Model Components may require additional Python packages to be installed within FIREWHEEL's virtual environment or for data to be downloaded.
In this case, the Model Component can have an ``INSTALL`` directory, which contains a valid `Ansible Playbook <https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html>`_ (recommended method).
Alternatively, ``INSTALL`` can be an executable script (as denoted by a `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ line), though this is not recommended and support will be removed in a future releases.
When users use the :ref:`helper_mc_generate` Helper, a new INSTALL directory is created with sample ``tasks.yml`` and ``vars.yml`` automatically included.


When a repository is installed via the :ref:`helper_repository_install` Helper, users have the option to automatically run each MC's INSTALL script using the ``-s`` flag (see :ref:`helper_repository_install` for more details).
Alternatively, if an uninstalled model component is used in a firewheel :ref:`helper_experiment`, then it will prompt the user to install the model component.

*****************
Design Principles
*****************

We recommend that the following principles are adhered to when installing a model component.

1. `Idempotence <https://en.wikipedia.org/wiki/Idempotence>`_ -- The file(s) should be capable of running multiple times without causing issues. This is a core tenant of Ansible and a strong motivator why Ansible playbooks are the preferred method.
2. **Reproducibility** -- It is critical that users download the exact same data that was originally intended by the Model Component creators.
   If the data/packages differ, then there is a strong possibility that the experimental outcomes will differ and could produce unintended consequences.
   Therefore, we strongly recommend that MC creators link to exact versions of software to download, rather than an automatically updating link.
   For example, if the MC was supposed to install a GitLab runner:

   .. code-block:: bash

        # BAD: This will automatically get the latest URL.
        wget https://gitlab-runner-downloads.s3.amazonaws.com/latest/binaries/gitlab-runner-linux-amd64

        # GOOD: Get version 11.4.2
        wget https://s3.amazonaws.com/gitlab-runner-downloads/v11.4.2/binaries/gitlab-runner-linux-386

3. **Integrity** -- A checksum for all downloaded files is strongly recommend both to facilitate reproducibility and to increase the security of the experiment.
4. **Offline Accessible** -- Many experiments are conducted on infrastructure that lacks Internet access. Therefore, we recommend that INSTALL files allow users to achieve the same end result using cached files.
5. **Cleanup** -- Only the essential dependencies should be kept and any irrelevant data that may have been generated during intermediate steps should be removed.
6. **Readability** -- Users will need to execute these potentially unknown actions, the INSTALL script should be well documented and readable to the average user. Readability is desired over brevity.


.. _mc_install_ansible:

**************************************
Ansible INSTALL Directory Requirements
**************************************

The expected ``INSTALL`` directory structure is::

  MC_DIR
  └── INSTALL
      ├── tasks.yml
      └── vars.yml

Where ``tasks.yml`` is a YAML list of Ansible tasks that will be `included <https://docs.ansible.com/ansible/latest/collections/ansible/builtin/include_tasks_module.html>`__ when installing the model component.
The ``vars.yml`` file should be a YAML dictionary of all the variable keys/values which will be used when installing the model component.

``tasks.yml``
=============
The tasks file should be a YAML list with any tasks needed to ensure that the model component can execute correctly as intended.

.. code-block:: yaml
  :caption: This is an example ``tasks.yml`` file that collects, verifies, and compresses needed binaries.


   - name: Create directory for htop
     ansible.builtin.file:
       path: "htop-1_0_2_debs"
       state: directory

   - name: Download htop Package
     ansible.builtin.get_url:
       url: "http://archive.ubuntu.com/ubuntu/pool/universe/h/htop/htop_1.0.2-3_amd64.deb"
       dest: "htop-1_0_2_debs/htop_1.0.2-3_amd64.deb"
       checksum: "sha256:0311d8a26689935ca53e8e9252cb2d95a1fdc2f8278f4edb5733f555dad984a9"

   - name: Create tarball of htop directory
     ansible.builtin.archive:
       path: "htop-1_0_2_debs"
       dest: "htop-1_0_2_debs.tar.gz"
       format: gz

   - name: Move tarball to vm_resources/debs/
     ansible.builtin.copy:
       src: "htop-1_0_2_debs.tar.gz"
       dest: "{{ mc_dir }}/vm_resources/debs/htop-1_0_2_debs.tgz"

   - name: Remove htop directory
     ansible.builtin.file:
       path: "htop-1_0_2_debs"
       state: absent


``vars.yml``
============

The ``vars.yml`` file should be a YAML dictionary of all the variable keys/values which will be used when installing the model component.
FIREWHEEL will automatically provide the following variables to the Ansible playbooks when running:

- ``mc_name`` -- The name of the Model Component.
- ``mc_dir`` -- The full path to the model component directory.

In addition to any variables the specific tasks need, the ``vars.yml`` *should* have a ``required_files`` key where a list of the final output files is listed.
This is because the model component installation is assumed to be complete when all ``required_files`` are present.
As an added benefit, FIREWHEEL supports caching pre-computed blobs from various resources to enable offline experiment access and the ``required_files`` supports this feature.
The process of collecting offline required files is automatically handled by FIREWHEEL and using this process is discussed in detail in :ref:`mc_install_cache`.
If no ``required_files`` are needed, then it can be omitted from ``INSTALL/vars.yml``.

Continuing the example from above, the end result of ``tasks.yml`` is the creation of the file ``{{ mc_dir }}/vm_resources/debs/htop-1_0_2_debs.tgz``.
Therefore, this file is *required* to exist for the model component to be completely installed.
The ``vars.yml`` file would look like:

.. code-block:: yaml
  :caption: This is an example ``vars.yml`` file that ensures the final MC state.

  required_files:
    - destination: "{{ mc_dir }}/vm_resources/debs/htop-1_0_2_debs.tgz"


The full definition for ``required_files`` is:

.. confval:: destination

    Where the file should be placed.
    Should include ``{{ mc_dir }}`` if the file needs to be relative to the model component directory.

    :type: string
    :required: true

.. confval:: source

    Where the file should be located **within** the cache.
    This should not be set by MC creators, as it defaults to ``{{ mc_name }}/file``.
    However, it is available to be modified by end-users if desired.

    :type: string
    :required: false
    :default: ``{{ mc_name }}/file``

.. confval:: checksum_algorithm

    Algorithm to determine checksum of file.
    Must be supported by `ansible.builtin.stat <https://docs.ansible.com/ansible/latest/collections/ansible/builtin/stat_module.html#parameter-checksum_algorithm>`_ (e.g, ``"sha1"``, ``"sha256"``, etc.).

    :type: string
    :required: false


.. confval:: checksum

    The hash of the file.

    .. warning::

      While having a `reproducible build <https://reproducible-builds.org/>`_ process (and a stable checksum/hash) is ideal for cyber experimentation, there are many challenges to achieving this reality. Notably, many `archive tools <https://reproducible-builds.org/docs/archives/>`_ include metadata, such as timestamps, that make it difficult to create an identical checksum each time. Unless these issues have been addressed within ``tasks.yml``, this field should be avoided. For more information, see: https://reproducible-builds.org/.

    :type: string
    :required: false

.. _mc_install_cache:

***************************
Setting up an Offline Cache
***************************

Collecting and retrieving files from a cache is automatically supported in Ansible playbooks without MC designer intervention.
Currently, FIREWHEEL supports caching files in a file server, git repository, or in an Amazon S3 data store.
If the user sets the necessary settings in the :ref:`firewheel_configuration` for the described types below, then FIREWHEEL will automatically check those locations for any model component ``required_files``.
Users are able to set multiple cache types as FIREWHEEL will check any caches for the required file.

Users setting up a cache should place cached files using the path: ``{{ mc_name }}/{{ item.destination | basename }}``.
From the example above, the default ``source`` path would be ``linux.ubuntu/htop-1_0_2_debs.tgz``, where ``linux.ubuntu`` is the name of the associated model component.
Users can optionally modify this path by setting the :confval:`source` within the model component variables file.

Git Cache
=========
Users can use `git <https://git-scm.com>`__ repositories for caching model component binaries.
To use this, users will need to install  `git <https://git-scm.com>`__ and `git-lfs <https://git-lfs.com>`__ on their :ref:`cluster-control-node` to appropriately clone their repositories.
This caching mechanism is set up so that repositories are initially cloned *without* downloading any large file storage (LFS) for performance reasons.
Then if a ``required_file`` is identified without that repository, the file is subsequently downloaded and moved into place.

.. note::

  Users may also need to execute ``git lfs install`` to set up Git LFS for their user account.

If users plan to use git repositories for the Model Component cache, they should specify the following options in the :ref:`firewheel_configuration` under the ``ansible`` key.

An example of this configuration is shown below:

.. code-block:: yaml
  :caption: An example of an Ansible git server portion of the :ref:`firewheel_configuration`.


  ansible:
    git_servers:
      - server_url: "https://github.com"
        repositories:
          - path: "firewheel/mc_repo1"
          - path: "firewheel/mc_repo2"
            branch: "develop"
      - server_url: "ssh://git@gitlab.com"
        repositories:
          - path: "emulytics/firewheel/mc_repo3"
            branch: "feature-branch"
      - server_url: "https://user:ACCESS-TOKEN@github.com/"
        repositories:
          - path: "firewheel/mc_repo4"

.. confval:: git_servers

    A list of dictionaries containing configuration options for multiple Git servers.

    :type: list
    :required: true

    Each dictionary should contain the following keys:

    .. confval:: server_url

        The full URL of the git server (e.g., ``"https://github.com"``).

        :type: string
        :required: true

        .. note::

            If an access token is being used, the user can specify it as part of the URL.
            For example: ``https://user:ACCESS-TOKEN@github.com/user/repo.git``

    .. confval:: repositories

        :type: list
        :required: true

        A list of repositories associated with the Git server. Each repository is represented as a dictionary containing the following keys:

        .. confval:: path

            The path to the git repository containing the cached files. SCP-style URLs are **not** supported.
            When using the ``ssh://`` protocol, please use the following format: ``ssh://username@example.com``.

            :type: string
            :required: true

        .. confval:: branch

            The version of the repository to check out. This can be the literal string ``HEAD``, a branch name, or a tag name. This is passed to `ansible.builtin.git <https://docs.ansible.com/ansible/latest/collections/ansible/builtin/git_module.html#parameter-version>`_.

            :type: string
            :required: false
            :default: ``"HEAD"``


S3 Cache
========
Users can use `Amazon Simple Storage Service (S3) <https://aws.amazon.com/s3/>`__ buckets for caching model component binaries.
To use this, users will need to install  `boto3 <https://pypi.org/project/boto3/>`__, the official Amazon Web Services (AWS) Software Development Kit (SDK) for Python into their FIREWHEEL virtual environment.
Additionally, if users plan to use an AWS S3 instance for the Model Component cache, they should specify the following options in the :ref:`firewheel_configuration` under the ``ansible`` key.

An example of this configuration is shown below:

.. code-block:: yaml
  :caption: An example of an Ansible S3 portion of the :ref:`firewheel_configuration`.


  ansible:
    s3_endpoints:
      - s3_endpoint: "https://s3.us-east-1.amazonaws.com"
        aws_access_key_id: "AKIAIOSFODNN7EXAMPLE"
        aws_secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        buckets:
          - "firewheel_bucket1"
          - "firewheel_bucket2"
      - s3_endpoint: "https://custom-s3-endpoint:8000"
        aws_access_key_id: "AJIAIOSFODNN7EXAMPLE"
        aws_secret_access_key: "wKalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        buckets:
          - "firewheel_bucket3"

.. confval:: s3_endpoints

    A list of dictionaries containing configuration options for multiple S3 endpoints.

    :type: list
    :required: true

    Each dictionary should contain the following keys:

    .. confval:: s3_endpoint

        The full URL of the S3 instance (e.g., ``"s3.amazonaws.com"``).

        :type: string
        :required: true

    .. confval:: aws_access_key_id

        The `AWS access key <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html>`_ (e.g., ``"AKIAIOSFODNN7EXAMPLE"``).

        :type: string
        :required: true

    .. confval:: aws_secret_access_key

        The `AWS secret key <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html>`_ (e.g., ``"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"``).

        :type: string
        :required: true

    .. confval:: s3_buckets

        A list of buckets associated with the S3 server where each bucket is represented as a string.

        :type: list
        :required: true

File Server Cache
=================
If users plan to use a file server (HTTP/HTTPS/FTP) for the Model Component cache, they can specify the following options in the :ref:`firewheel_configuration` under the ``ansible`` key.

An example of this configuration is shown below:

.. code-block:: yaml
  :caption: An example of an Ansible file server portion of the :ref:`firewheel_configuration`.

  ansible:
    file_servers:
      - url: "http://example.com"
        cache_paths:
          - "path/to/location"
          - "path/to/other/location"
      - url: "http://secondexample.com"
        use_proxy: True
        validate_certs: False
        cache_paths:
          - "secondpath/to/file"


.. confval:: file_servers

    A list of dictionaries containing configuration options for multiple file servers.

    :type: list
    :required: true

    Each dictionary should contain the following keys:

    .. confval:: url

        The URL of the server hosting the cached files.

        :type: string
        :required: true

        .. note::

            If you are using an username or password token, you can specify it in the URL.
            For example: ``https://user:password@server.com``


    .. confval:: cache_paths

        A list of intermediate paths to the FIREWHEEL cache. For example in the URL ``http://example.com/files/firewheel/firewheel_repo_linux/linux.ubuntu/htop-1_0_2_debs.tgz`` then ``url="http://example.com"``,  ``url_cache_path="files/firewheel/firewheel_repo_linux"``, and the ``source=linux.ubuntu/htop-1_0_2_debs.tgz``.
        If no cache path is required, please use a list with empty string entry as the value.

        .. code-block:: yaml

          file_servers:
            - url: "http://example.com"
              cache_paths:
                - ""

        :type: list
        :required: true


    .. confval:: use_proxy

        If ``false``, it will not use a proxy, even if one is defined in an environment variable on the target hosts.

        :type: boolean
        :required: false
        :default: true

    .. confval:: validate_certs

        If ``false``, SSL certificates will not be validated.

        :type: boolean
        :required: false
        :default: true

********************************
Script INSTALL File Requirements
********************************

.. warning::

  This method is **NOT** recommended and will be eliminated in future releases of FIREWHEEL.

If the model component needs to use a single executable to install additional Model Component, users must create a single file called: ``INSTALL`` that should not have an extension and contains a `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ line (e.g., ``#!/bin/bash``).
Additionally, users must ensure that, upon successful installation, a new file is created in the model component directory with the following format: ``.<MC Name>.installed``.
For example, if the model component name is ``dns.dns_objects`` than the new file would be ``.dns.dns_objects.installed``.

.. dropdown:: A Bash-based INSTALL template

    .. code-block:: bash
        :caption: This is an example INSTALL file using bash scripting. By replacing ``{{mc_name}}`` with the model component name, users can modify this example.

        #!/bin/bash

        #######################################################
        # This is a sample install file for {{mc_name}}.
        # This file can be used to perform one-time actions
        # which help prepare the model component for use.
        #
        # Common uses of INSTALL files include downloading
        # VM Resources from the Internet and installing new
        # Python packages into FIREWHEEL's virtual environment.
        #
        # NOTE: When you are creating these files, it is
        # imperative that specific versions of software are
        # used. Without being as specific as possible,
        # experimental results will **NOT** be repeatable.
        # We strongly recommend that any changes to software
        # versions are accompanied by a warning and new model
        # component version.
        #######################################################

        # Create a flag for verifying installation
        SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
        INSTALL_FLAG=$SCRIPT_DIR/.{{mc_name}}.installed

        #######################################################
        # Checking if there this script has already been complete.
        #######################################################
        function check_flag() {
            if [[ -f "$INSTALL_FLAG" ]]; then
                echo >&2 "{{mc_name}} is already installed!"
                exit 117;  # Structure needs cleaning
            fi
        }


        #######################################################
        # Install python packages into the virtual environment
        # used by FIREWHEEL. This takes in an array of packages.
        #######################################################
        function install_python_package() {
            pkgs=("$@")
            for i in "${pkgs[@]}";
            do
                python -m pip install "$i"
            done
        }


        #######################################################
        # Download using wget and then checksum the downloaded files.
        #
        # It is important to verify that the downloaded files
        # are the files are the same ones as expected.
        # This function provides an outline of how to checksum files,
        # but will need to be updated with the specific hashes/file names
        # that have been downloaded.
        #
        # This function assumes that the passed in hashes are SHA-256
        #######################################################
        function wget_and_checksum() {
            downloads=("$@")
            # Uses 2D arrays in bash: https://stackoverflow.com/a/44831174
            declare -n d
            for d in "${downloads[@]}";
            do
                wget "${d[0]}"
                echo "${d[1]}  ${d[2]}" | shasum -a 256 --check || return 1
            done
        }


        #######################################################
        # A function to help users clean up a partial installation
        # in the event of an error.
        #######################################################
        function cleanup() {
            echo "Cleaning up {{mc_name}} install"
            # TODO: Cleanup any downloaded files
            # rm -rf file.tar
            rm -rf $INSTALL_FLAG
            exit 1
        }
        trap cleanup ERR

        # Start to run the script

        # Ensure we only complete the script once
        check_flag

        #######################################################
        # Uncomment if there are Pip packages to install
        # `pip_packages` should be space separated strings of
        # the packages to install
        #######################################################
        # pip_packages=("requests" "pandas")
        # install_python_package "${pip_packages[@]}"


        #######################################################
        # Uncomment if there is data/VM resources/images to download.
        # `file1`, `file2`, etc. should be space separated strings of
        # (URL SHASUM-256 FILENAME).
        #
        # We recommend that explicit versions are used for all Images/VMRs to prevent
        # possible differences between instances of a given Model Component.
        # Please be mindful of the software versions as it can have unintended
        # consequences on your Emulytics experiment.
        #
        # We require checksums of the files to assist users in verifying
        # that they have downloaded the same version.
        #######################################################
        # Be sure to use SHA-256 hashes for the checksums (e.g. shasum -a 256 <file>)
        # file1=("url1" "e0287e6339a4e77232a32725bacc7846216a1638faba62618a524a6613823df5" "file1")
        # file2=("url2" "53669e1ee7d8666f24f82cb4eb561352a228b1136a956386cd315c9291e59d59" "file2")
        # files=(file1 file2)
        # wget_and_checksum "${files[@]}"
        # echo "Downloaded and checksummed all files!"


        #######################################################
        # Add any other desired configuration/packaging here
        #######################################################
        echo "The {{mc_name}} INSTALL file currently doesn't do anything!"

        # Set the flag to notify of successful completion
        touch $INSTALL_FLAG

