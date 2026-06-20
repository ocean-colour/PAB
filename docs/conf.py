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
    "myst_parser",              # render Markdown (design docs)
    "sphinxcontrib.mermaid",    # mermaid diagrams in the design doc
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "PDFs"]

# The Markdown design/reference docs are authored as standalone GitHub
# documents with repo-relative links (e.g. ``../../pab/``); these are not
# Sphinx cross-reference targets, so do not fail the build on them.
suppress_warnings = ["myst.xref_missing"]

# Treat both .rst and .md as sources.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

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
