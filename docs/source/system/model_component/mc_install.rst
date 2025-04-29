.. _mc_install:

############################
Model Component INSTALL file
############################

Some Model Components may require additional Python packages to be installed within FIREWHEEL's virtual environment or for data to be downloaded.
In this case, the Model Component can have an ``INSTALL`` file, which can be any executable script (as denoted by a `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ line).

When creating an INSTALL file, it is critical that users will download the exact same data that was originally intended by the Model Component creators.
If the data/packages differ, than there is a strong possibly that the experimental outcomes will differ and could produce unintended consequences.
Therefore, we strongly recommend that MC creators link to exact versions of software to download, rather than an automatically updating link.
For example, if the MC was supposed to install a GitLab runner:

.. code-block:: bash

    # This will automatically get the latest URL, this is BAD
    wget https://gitlab-runner-downloads.s3.amazonaws.com/latest/binaries/gitlab-runner-linux-amd64

    # This will get a specific version, this is GOOD!
    wget https://s3.amazonaws.com/gitlab-runner-downloads/v11.4.2/binaries/gitlab-runner-linux-386

In addition to linking to a specific version, we strongly recommend also using a SHA-256 checksum to verify the downloaded file.

When a repository is installed via the :ref:`helper_repository_install` Helper, users have the option to can automatically run each MCs INSTALL script using the ``-s`` flag (see :ref:`helper_repository_install` for more details).

****************
INSTALL Template
****************

The file ``src/firewheel/control/utils/templates/INSTALL.template`` contains a template for a Bash-based INSTALL file.
When users use the :ref:`helper_mc_generate` Helper, this file is automatically added to the MC directory.
The current template is shown below.

.. literalinclude:: ../../../src/firewheel/control/utils/templates/INSTALL.template
    :language: bash
    :caption: INSTALL template
    :name: INSTALL
