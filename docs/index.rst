PAB documentation
=================

**PAB** produces matchup analyses between **PACE** (satellite ocean color) and
**BGC-Argo** (autonomous float) data, and shares the results with the
community.

This site is the developer and methods documentation. It is built with Sphinx
and grows one page per development stage (see the
:doc:`coding plan <design/PAB_coding_plan>`). The community-facing reporting
site is a separate Sphinx target produced in Stage 7.

.. toctree::
   :maxdepth: 1
   :caption: Getting started

   dev_setup

.. toctree::
   :maxdepth: 1
   :caption: Package

   db_schema
   argo_ingestion
   pace_access
   matchup
   fitting

.. toctree::
   :maxdepth: 1
   :caption: Notebooks

   nb/00_getting_started
   nb/01_database_layer
   nb/02_argo_mld_summary
   nb/03_pace_access
   nb/04_matchup
   nb/06_fit

.. toctree::
   :maxdepth: 1
   :caption: Design

   design/PAB_design
   design/PAB_coding_plan
   design/PAB_implementation

.. toctree::
   :maxdepth: 1
   :caption: Reference

   context

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
