.. _contributor_guide:

Contributor Guide
=================

FIREWHEEL is an open source project and we welcome contributions from the community.
New ideas and better solutions to existing code are always welcome!
Here is how you can get started:

#. **Submit issue** request.
   We encourage users to submit bug reports and feature requests via the issue tracker.
   If the idea is new/complex we recommend that the idea is discussed via the bug report before implementation.
   This first allows the FIREWHEEL community to arrive at consensus on the idea before time is spent implementing it.

#. **Fork** FIREWHEEL to create your own copy of the project.

#. **Create a branch** for the feature you want to work on.
   Please use a sensible name such as 'fix-for-issue-123' or 'feat-my-new-feature'.
   Commit as you progress (``git add`` and ``git commit``).
   Use descriptive commit messages.
   Review the `Deprecation policy`_ to identify potential impact to users.

#. **Lint** your contribution.
   See `Development Style`_ for information on how to ensure correct formatting.

#. **Document** changes.
   If your change introduces any new features, please update (or create) appropriate documentation in ``doc/source``.
   It's difficult to keep documentation up-to-date, so there is an emphasis on ensuring that revisions and especially new functionality is well documented.

#. **Test** your contribution.
   Ensure you have FIREWHEEL installed (with your changes) and then run the test suite (both unit and functional) locally (see `Testing`_ for details).
   Running the tests locally *before* submitting a pull request helps catch problems early and reduces the load on the continuous integration system.
   To ensure you have a properly-configured development environment for running the tests, see `Build environment setup`_.
   If possible/necessary, new unit and/or functional tests should be added to ensure that the feature/bug is fully fixed.

#. **Submit** your contribution as a new Pull Request to the main branch.
   We are following `Conventional Commits <https://www.conventionalcommits.org>`_ for pull request titles (e.g., ``feat: My new feature``.
   The available types include:

   - ``feat``: A new feature
   - ``fix`` or ``bug``: A bug fix
   - ``docs`` or ``doc`` or ``documentation``: Documentation only changes
   - ``style``: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc.)
   - ``refactor``: A code change that neither fixes a bug nor adds a feature
   - ``perf``: A code change that improves performance
   - ``test`` or ``tests`` or ``testing``: Adding missing tests or correcting existing tests
   - ``build``: Changes that affect the build system or external dependencies (example scopes: minimega, discovery)
   - ``ci``: Changes to our CI configuration files and scripts (example scopes: GitLab, GitHub)
   - ``chore``: Other changes that don't modify src or test files
   - ``revert``: Reverts a previous commit
   - ``deps`` or ``dependencies``: Changes that updates dependencies
   - ``sec`` or ``security``: Changes that impact security of the system
   - ``deprecate``: Changes that deprecate some feature
   
   Please include an appropriate summary of the work and reference any issues which will be resolved.
   For example, if the PR will address bug, also add "Fixes #123" where 123 is the issue number.
   If your code is not ready to merge, but you want to get feedback, please consider marking it as a draft.
   That way we will all know that it's not yet ready to merge and that you may be interested in more fundamental comments about design.
   When you think the pull request is ready to merge, remove the draft marking.

#. **Wait for review**.
   When a pull request is made, at least one reviewer (the other developers and interested community members) will assess the code and write inline and/or general comments on your Pull Request (PR) to help you improve its implementation, documentation, and style.
   Every single developer working on the project has their code reviewed, and we've come to see it as friendly conversation from which we all learn and the overall code quality benefits.
   Therefore, please don't let the review discourage you from contributing: its only aim is to improve the quality of project, not to criticize (we are, after all, very grateful for the time you're donating!).
   Once the code has been reviewed and all comments have been addressed, the reviewer will authorize the patch with a 'LGTM' (looks good to me) phrase.
   After authorization, any code maintainers may merge the pull request.


Build environment setup
-----------------------

#. You will need to install all of FIREWHEEL's dependencies (see the :ref:`quickstart-guide` guide).

#. Clone your fork of the FIREWHEEL repository.

#. Once it is cloned, you should create up a Python development environment tailored for FIREWHEEL.
   We highly recommend using a virtual environment and provide instructions for ``venv``::

      # Create a virtualenv named ``fwpy`` that lives in the directory of the same name
      python -m venv fwpy
      # Activate it
      source fwpy/bin/activate

#. Install your modified copy of FIREWHEEL into the virtual environment and finish configuring FIREWHEEL.

   * If you need to fully install/configure FIREWHEEL in development mode, you can use the ``install.sh`` script with the ``-d`` flag to install development dependencies. ::

      # If you would like to change any default
      # configuration options in ``provision_env.sh``
      # please change those first.
      ./install.sh -d

   * If you just need to install FIREWHEEL's development dependencies you can use::

      python -m pip install firewheel[dev]

#. FIREWHEEL will now be install/configured using your version of the code.


Development Style
-----------------

Due to the complexity of FIREWHEEL, it is important to ensure that code is readable and maintainable.
As such, we have certain guidelines that should be followed:

* FIREWHEEL should always be all caps. This helps distinguish it from the CLI invocation.
* FIREWHEEL components *Control*, *VM Resource Manager*, and *Lib* should always be title case and italicized.
* When referring to a FIREWHEEL CLI Helper, the term "Helper" should be capitalized.
* All code must pass our `tox <https://tox.wiki/en/latest/>`__ linting process.
  We use numerous tools to ensure high-quality code including `ruff <https://docs.astral.sh/ruff>`_, `flake8 <https://flake8.pycqa.org/en/latest/>`_, and several others.
  You can run our linting suite by installing FIREWHEEL with development mode (see `Build environment setup`_)
  Then you can run tox::

    tox -e lint,lint-docs

  If your test fails on formatting, you can run:

  .. code-block:: bash

      tox -e format

* All new code should have tests.
  Most new code will require unit tests.
  Some features, e.g. those impacting in-experiment features, may also require functional tests.
* All code should be documented.
  We use Google Style docstrings and you can review an example `here <https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html>`_.
* We use `reStructuredText <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_ and `Sphinx <https://www.sphinx-doc.org/en/master/>`_ to build documentation.
* Documentation in RST files should be sentence/phrase new-line separated.
  That is, each line in the RST file should be a single phrase or sentence.
  Please see the raw version of this file as an example.
* All changes are reviewed.
  Ask on the mailing list (firewheel [at] sandia [dot] gov) if you get no response to your pull request.


Testing
-------

FIREWHEEL has a robust test suite that hopefully ensures correct execution.
There are unit tests, which validates that various classes/methods/functions execute as designed, and functional tests which validate that experiments are launched as expected.
The test suite has to pass before a pull request can be merged, and tests should be added to cover any modifications to the code base.

While most existing unit test cases are written using  `unittest <https://docs.python.org/3/library/unittest.html>`_, users are welcome to write new tests in either  `unittest <https://docs.python.org/3/library/unittest.html>`_ or with the `pytest <https://docs.pytest.org/en/latest/>`_ testing framework. Using `pytest <https://docs.pytest.org/en/latest/>`_ may require some minor modifications to the current test suite.
All tests should be located in the appropriate folder under ``firewheel/src/tests``.

Our tests can be executed either via `tox <https://tox.wiki/en/latest/>`_ or using our FIREWHEEL test helpers. ::

   firewheel test unit
   firewheel test e2e

Test coverage
-------------

Tests for a module should ideally cover all code in that module, i.e., statement coverage should be at 100%.

To measure the test coverage, install FIREWHEEL with development dependencies and then run::

  tox -e py39

This will generate a `coverage <https://coverage.readthedocs.io/en/latest/>`_ report and also exit if the tests fail.


.. _deprecation_policy:

Deprecation policy
------------------

If the behavior of the library has to be changed, a deprecation cycle must be
followed to warn users.

A deprecation cycle is *not* necessary when:

* adding a new function, or
* adding a new keyword argument to the *end* of a function signature, or
* fixing buggy behavior

A deprecation cycle is necessary for *any breaking API change*, meaning a
change where the function, invoked with the same arguments, would return a
different result after the change.

.. note::

  For FIREWHEEL, we consider our API as any function, class, method which are commonly and directly used by model components.

This includes:

* changing the order of arguments or keyword arguments, or
* adding arguments or keyword arguments to a function, or
* changing the name of a function, class, method, etc., or
* moving a function, class, etc. to a different module, or
* changing the default value of a function's arguments.

Usually, our policy is to put in place a deprecation cycle over two releases.

Note that the 2-release deprecation cycle is not a strict rule and in some
cases, the developers can agree on a different procedure upon justification
(like when we can't detect the change, or it involves moving or deleting an
entire function for example).

Code Of Conduct
---------------
The FIREWHEEL community has adopted a Code Of Conduct to ensure that we have an open, welcoming, diverse, inclusive, and healthy community.
Please review :ref:`CODE_OF_CONDUCT <conduct>` for more information.

Copyright
---------
If you are submitting a patch to the existing codebase, the code will be licensed under the same license as FIREWHEEL.
Please review :ref:`LICENSE <license>` for more information.
