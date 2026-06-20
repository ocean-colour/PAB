Developer setup & contributing
==============================

This page covers how to set up a development environment, run the tests, and
build the docs. PAB targets **Python ≥ 3.12**.

Installation
------------

Clone the repository and install the package (editable) plus its dependencies::

    git clone https://github.com/ocean-colour/PAB.git
    cd PAB
    pip install -r requirements.txt
    pip install -e .

``requirements.txt`` is the **single source of dependencies**. Three
scientific packages install from sources other than PyPI and are listed (as
comments) at the bottom of that file:

* **bing** — Bayesian IOP retrieval (being packaged for PyPI; install from
  source until then);
* **remote_sensing** — Earthdata Cloud discovery/access helpers
  (``pip install git+https://github.com/<owner>/remote_sensing``);
* **ocpy** — ocean-color utilities and dataset loaders (GitHub or a local
  checkout).

These are intentionally not in the ``pip install -r`` set so a fresh install
does not fail; install them separately for the stages that need them
(Stages 2–7). The Stage 0 import smoke test and the docs build do **not**
require them.

Running the tests
-----------------

The suite runs offline (no network/S3; the PACE cloud layer is mocked)::

    pytest

Configuration lives in ``pytest.ini``; tests are collected from ``pab/tests``.

Building the docs
-----------------

::

    pip install sphinx sphinx-rtd-theme myst-parser sphinxcontrib-mermaid
    sphinx-build -b html docs docs/_build/html

Open ``docs/_build/html/index.html``. The build mocks the heavy optional
imports (``bing``, ``ocpy``, …) so it succeeds without them.

Code style
----------

* Google-style docstrings on every public function.
* ``ruff``/``black``-compatible formatting (config in ``ruff.toml``);
  run ``ruff check pab`` and ``ruff format pab``.
* Type hints where they aid clarity.

Working agreements
------------------

* **Git is handled by the user.** Do not run state-changing git commands.
* **Python only** — no MATLAB.
* **Every stage ships code + tests + docs**; a stage is "done" only when its
  functionality is tested (pytest) and documented.

Continuous integration
-----------------------

GitHub Actions runs the ``pytest`` suite **and** a docs build on every push
and pull request (see ``.github/workflows/ci.yml``).
