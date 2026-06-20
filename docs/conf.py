"""Sphinx configuration for the PAB documentation site."""

import os
import sys

# Make the ``pab`` package importable for autodoc.
sys.path.insert(0, os.path.abspath(".."))

from pab import pab_version  # noqa: E402

# -- Project information -----------------------------------------------------
project = "PAB"
author = "J. Xavier Prochaska and collaborators"
copyright = "2026, " + author
release = pab_version
version = pab_version

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",      # Google-style docstrings
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    # myst-nb bundles myst-parser (Markdown) and adds notebook (.ipynb) support;
    # load it INSTEAD of myst_parser (loading both conflicts).
    "myst_nb",
    "sphinxcontrib.mermaid",    # mermaid diagrams in the design doc
]

templates_path = ["_templates"]
# The notebooks in docs/nb/ are rendered into the site (see the Notebooks
# toctree); only nb/README.md (a repo-facing index, not a docs page) is excluded.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "PDFs", "nb/README.md"]

# The Markdown design/reference docs are authored as standalone GitHub
# documents with repo-relative links (e.g. ``../../pab/``); these are not
# Sphinx cross-reference targets, so do not fail the build on them.
suppress_warnings = ["myst.xref_missing"]

# Treat .rst, .md, and .ipynb as sources (.ipynb via myst-nb).
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "myst-nb",
    ".ipynb": "myst-nb",
}

# Do NOT execute notebooks at build time — use the outputs already committed
# (some notebooks have optional live-data cells guarded by a RUN_LIVE flag).
nb_execution_mode = "off"

# Render ```mermaid fenced code blocks (in the Markdown design docs) as
# mermaid directives via sphinxcontrib.mermaid.
myst_fence_as_directive = ["mermaid"]

# Napoleon (Google-style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = False

# Autodoc: do not fail the build if optional heavy deps are missing.
autodoc_mock_imports = [
    "bing",
    "ocpy",
    "remote_sensing",
    "argopy",
    "earthaccess",
    "gsw",
    "healpy",
    "bokeh",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- HTML output -------------------------------------------------------------
try:
    import sphinx_rtd_theme  # noqa: F401

    html_theme = "sphinx_rtd_theme"
except ImportError:
    html_theme = "alabaster"

html_static_path = ["_static"]
