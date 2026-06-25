"""Reporting layer.

Programmatic .rst generation, standalone Bokeh figures/tables,
region/season + HEALPix aggregation, and exports / publish backends
(Nautilus S3 upload + manifest, Zenodo packaging — stubbed for now).

Public API::

    from pab.report import aggregate, rst, interactive, publish

Implemented in Stage 7.
"""

from pab.report import aggregate, interactive, publish, rst
from pab.report.aggregate import aggregate_by, aggregate_healpix
from pab.report.publish import build_manifest, export_tables, publish_release
from pab.report.rst import build_site

__all__ = [
    "aggregate",
    "interactive",
    "publish",
    "rst",
    "aggregate_by",
    "aggregate_healpix",
    "build_manifest",
    "export_tables",
    "publish_release",
    "build_site",
]
