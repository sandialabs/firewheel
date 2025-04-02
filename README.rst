#########
FIREWHEEL
#########

.. image:: https://sandialabs.github.io/firewheel/_static/logo_horizontal.png

.. image:: https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%7C%203.11%7C%203.12%7C%203.13-blue
    :target: https://pypi.org/project/firewheel/
.. image:: https://www.bestpractices.dev/projects/9722/badge
   :target: https://www.bestpractices.dev/projects/9722
.. image:: https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg
    :target: https://sandialabs.github.io/firewheel/developer/code_of_conduct.html

.. readme-inclusion-marker

FIREWHEEL is an experiment orchestration tool that assists a user in building and controlling, repeatable experiments of distributed network systems at any scale.

FIREWHEEL was developed as part of Sandia National Laboratories `Emulytics <https://www.sandia.gov/emulytics>`_ program.
With FIREWHEEL, users can easily construct modular parts of a cyber system, called *Model Components*.
These *Model Components* can be combined to form an experiment.
Most experiments are then instantiated using an emulation tool, such as `minimega <https://www.sandia.gov/minimega>`_.
Actions can be scheduled to occur within the experiment to enable fully automated experimentation.
FIREWHEEL enables easily logging the results of these actions so that they can be analyzed.
Therefore, it is trivial to run hundreds of experiments and collect results on the outcome.

***************
Getting Started
***************

* For a crash course on key FIREWHEEL concepts and on using FIREWHEEL please see our `quickstart-guide <https://sandialabs.github.io/firewheel/quickstart.html>`_ guide.
* To learn why experimentation may be the right tool to answer certain kinds of questions (and when it is probably the wrong tool) review our documentation on `Cyber Experimentation <https://sandialabs.github.io/firewheel/emulytics.html>`_.
* An overview of FIREWHEEL including how FIREWHEEL can help a researcher implement high-quality emulation-based experiments, hardware requirements, software architecture, and known security security concerns is provided in our `System Overview <https://sandialabs.github.io/firewheel/system/index.html>`_.
* An in-depth review of important FIREWHEEL concepts, is located `here <https://sandialabs.github.io/firewheel/concepts.html>`__.
* The CLI reference documentation can be found `here <https://sandialabs.github.io/firewheel/cli/index.html>`__.


****************************
Questions, Feedback, or Bugs
****************************

If you have questions you'd like to ask the developers which our documentation does not answer, or feedback you'd like to provide, feel free to use the mailing list: ``firewheel AT sandia DOT gov``

Please report any bugs that you find on our GitHub page.
We happily accept pull requests (PR), big or small.
Please see the `Contributor Guide <https://sandialabs.github.io/firewheel/developer/contributing.html>`_ for more information.

Any security-related issues should be reported directly to the developers at: ``firewheel AT sandia DOT gov`` (see `SECURITY.md <https://sandialabs.github.io/firewheel/developer/security.html>`_) for more information.

*******
License
*******
Copyright 2024 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights in this software.

Please see `LICENSE <https://sandialabs.github.io/firewheel/developer/license.html>`_ for more information.

************************
Research Using FIREWHEEL
************************

To cite FIREWHEEL please use the following publication:

Kasimir Georg Gabert, Adam Vail, Tan Q. Thai, Ian Burns, Michael J. McDonald, Steven Elliott, John Vivian Montoya, Jenna Marie Kallaher, and Stephen T. Jones. 2015. "Firewheel - A Platform for Cyber Analysis." United States. https://www.osti.gov/servlets/purl/1333803.

A non-comprehensive list of research/projects using FIREWHEEL includes:

- Sean Oesch, Amul Chaulagain, Brian Weber, Matthew Dixson, Amir Sadovnik, Benjamin Roberson, Cory Watson, and Phillipe Austria. 2024. "Towards a High Fidelity Training Environment for Autonomous Cyber Defense Agents." In Proceedings of the *17th Cyber Security Experimentation and Test Workshop (CSET '24)*. Association for Computing Machinery, New York, NY, USA, 91–99. https://doi.org/10.1145/3675741.3675752

- Michael Stickland, Justin D. Li, Thomas D. Tarman, and Laura Painton Swiler. 2021. "Uncertainty Quantification in Cyber Experimentation." United States. https://www.osti.gov/biblio/1867999.

- Michael Stickland, Justin D. Li, Laura Painton Swiler, and Thomas Tarman. 2021. "Foundations of Rigorous Cyber Experimentation." United States. https://www.osti.gov/biblio/1854751.

- Russell Van Dam, Thien-Nam Dinh, Christopher Cordi, Gregory Jacobus, Nicholas Pattengale, and Steven Elliott. 2019. "Proteus: A DLT-Agnostic Emulation and Analysis Framework." In *12th USENIX Workshop on Cyber Security Experimentation and Test (CSET 19)*, Santa Clara, CA. USENIX Association. https://www.usenix.org/conference/cset19/presentation/vandam.

- Nicholas D. Pattengale and David Rushton Farley. 2019. "Prototype Distributed Ledger Technology of UF6 Cylinder Tracking in Ethereum." United States. https://www.osti.gov/biblio/1770508.

- Laura Painton Swiler, Michael Stickland, and Thomas D. Tarman. 2019. "Design of Experiments for Cyber Experimentation." United States. https://www.osti.gov/biblio/1640123.

- Michael Stickland, Kasimir Georg Gabert, and John Jacobellis. 2017. "In Situ Training Environment for Autonomous Cyber." United States. https://www.osti.gov/biblio/1464674.

- Stephen T. Jones, Kasimir G. Gabert, and Thomas D. Tarman. 2017. "Evaluating Emulation-based Models of Distributed Computing Systems." United States. https://www.osti.gov/biblio/1398865.

- Isaac Polinsky. 2017. "A Platform for Developing and Evaluating Security Apps in Software Defined Networks." United States. https://www.osti.gov/biblio/1507916.

- John Frank Floren, Jerrold A. Friesen, Craig D. Ulmer, and Stephen T. Jones. 2017. "A Reference Architecture For Emulytics Clusters." United States. https://www.osti.gov/biblio/1823205.

- Kasimir Gabert, Ian Burns, Steven Elliott, Jenna Marie Kallaher, and Adam Vail. 2016. "Staghorn: An Automated Large-Scale Distributed System Analysis Platform." United States. https://www.osti.gov/biblio/1411885.
