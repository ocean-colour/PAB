"""NASA-GIOP rows carry the PRODUCT version, never the pipeline's.

Prompt 7 Task 3 ingested 1,367 rows stamped `2.0` because the driver passed
`config.pab_version`. That global read `1.1` during the v1 run and `2.0` during
v2, so one unchanged product ended up under two labels and "select the
NASA-GIOP baseline" became ambiguous. The rows were corrected by hand; these
tests stop it recurring.

The ingest is the same algorithm over the same official IOP granules whatever
version PAB is at, so its version only moves when *this ingest* changes (R6).
"""

from __future__ import annotations

import inspect


def test_product_version_is_pinned_and_not_the_pipeline_version():
    from pab.config import pab_version
    from pab.fit.nasa_giop import PRODUCT_VERSION

    assert PRODUCT_VERSION == "1.1"
    # The whole point: these are allowed to differ, and currently do.
    assert PRODUCT_VERSION != pab_version, (
        "PRODUCT_VERSION has drifted into equalling the pipeline version; the "
        "test can no longer detect the bug it was written for"
    )


def test_driver_does_not_stamp_the_pipeline_version():
    """The regression itself: `pab_version=config.pab_version` in the driver."""
    from pab.fit import nasa_giop

    src = inspect.getsource(nasa_giop.main)
    assert "pab_version=config.pab_version" not in src, (
        "the driver is stamping the PIPELINE version on NASA-GIOP rows again"
    )
    assert "pab_version=args.pab_version" in src


def test_cli_defaults_to_the_product_version():
    from pab.fit import nasa_giop

    p = nasa_giop._build_parser() if hasattr(nasa_giop, "_build_parser") else None
    if p is None:  # parser is built inline in main(); check the default text
        src = inspect.getsource(nasa_giop.main)
        assert "default=PRODUCT_VERSION" in src
    else:
        assert p.get_default("pab_version") == nasa_giop.PRODUCT_VERSION
