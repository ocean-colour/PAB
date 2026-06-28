"""Sphinx config for the PAB reporting site (generated; separate from the developer docs)."""
project = "PAB matchup results"
release = version = "0.0.dev0"
extensions = []
exclude_patterns = ["_build"]
try:
    import sphinx_rtd_theme  # noqa: F401

    html_theme = "sphinx_rtd_theme"
except ImportError:
    html_theme = "alabaster"
html_js_files = ['https://cdn.bokeh.org/bokeh/release/bokeh-3.7.2.min.js', 'https://cdn.bokeh.org/bokeh/release/bokeh-gl-3.7.2.min.js', 'https://cdn.bokeh.org/bokeh/release/bokeh-widgets-3.7.2.min.js', 'https://cdn.bokeh.org/bokeh/release/bokeh-tables-3.7.2.min.js', 'https://cdn.bokeh.org/bokeh/release/bokeh-mathjax-3.7.2.min.js']
# Per-matchup figures are copied under _static/figures and served verbatim.
html_static_path = ["_static"]
