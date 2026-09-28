"""The geometry pool must bound per-worker growth, exactly as ``match`` does.

Without ``max_tasks_per_child`` each worker's fsspec/HDF5 caches grow without
bound. Measured in-pod 2026-09-27 on a 12,251-granule run: workers went from
~2.5 GB each at 200 granules to ~6.8 GB each at 750 (~7.8 MB per granule per
worker), projecting to ~113 GB for the full run against a 64 Gi limit. The pod
OOMed and resumed repeatedly.

``match`` has carried this guard since the 1.0 run — its ``MAX_TASKS_PER_CHILD``
docstring records the same failure ("which is precisely how the pod died").
``geometry`` was written without it. This test stops the asymmetry coming back.
"""

from __future__ import annotations

import concurrent.futures

import pytest

from pab.matchup.engine import MAX_TASKS_PER_CHILD


def test_geometry_pool_sets_max_tasks_per_child(monkeypatch):
    """The pool is constructed with the recycle bound, not left unbounded."""
    from pab.matchup import geometry as G

    seen: dict = {}
    real = concurrent.futures.ProcessPoolExecutor

    class _Spy(real):  # type: ignore[misc,valid-type]
        def __init__(self, *a, **kw):
            seen.update(kw)
            # Run serially in-process: we are asserting on construction kwargs,
            # not exercising real workers.
            raise _Stop

    class _Stop(Exception):
        pass

    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", _Spy)

    with pytest.raises(_Stop):
        G._geometry_parallel(
            by_granule={"g1": [{"pixel_id": 1, "ix": 0, "iy": 0,
                                "latitude": 0.0, "longitude": 0.0}]},
            jobs=4,
            opener=None,
            tol_deg=G.DEFAULT_TOL_DEG,
            timeout_s=G.DEFAULT_TIMEOUT_S,
            record=lambda *a, **k: None,
            failed=[],
            gid={"g1": "g1"},
        )

    assert "max_tasks_per_child" in seen, (
        "geometry's pool is unbounded; each worker's fsspec/HDF5 caches will "
        "grow until the pod OOMs (measured ~7.8 MB per granule per worker)"
    )
    assert seen["max_tasks_per_child"] == MAX_TASKS_PER_CHILD
    assert seen["max_workers"] == 4


def test_geometry_and_match_agree_on_the_bound():
    """One constant, so the two stages cannot drift apart again."""
    import inspect

    from pab.matchup import geometry as G

    src = inspect.getsource(G._geometry_parallel)
    assert "MAX_TASKS_PER_CHILD" in src, (
        "geometry should reuse match's constant rather than hard-code a number"
    )
