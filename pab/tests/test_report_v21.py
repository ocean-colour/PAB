"""The 2.1 (normalized-geometry) report text: build_v2_1_rerun.md Task 4, V8 = A.

A store holding 2.0 (+ a 2.0.1 patch) and 2.1 fits must headline 2.1, state
the 2.0 → 2.1 geometry change once with a **computed** shift and the link to
``geometry_rerun.md``, and describe the forward-model domain for normalized
fits -- never the 2.0 "off-nadir, outside the trained geometry" sentence.
"""

from __future__ import annotations

import pytest

from pab.db.store import Store
from pab.metrics import compare
from pab.report import rst
from pab.tests.test_compare_versions import _add_bing_fit, _seed_patched_runaway


def _seed_21(store, *, ratio=1.2, geom="normalized"):
    """The patched runaway (2.0 + 2.0.1) plus its 2.1 re-fit on the same
    pixel at ``ratio`` × the 2.0.1 ``b_bp``, stamped ``geom_mode = geom``."""
    matchup_id, pixel_id, f20, f201 = _seed_patched_runaway(store)
    f21 = _add_bing_fit(
        store, matchup_id, pixel_id, version="2.1", bbp=4e-4 * ratio, chl=0.005
    )
    for fid, mode in ((f20, None), (f201, None), (f21, geom)):
        store.execute("UPDATE fits SET geom_mode = ? WHERE fit_id = ?", (mode, fid))
    for fid, bp in ((f20, 0.5), (f201, 0.015), (f21, 0.012)):
        store.upsert(
            "fit_results", {"fit_id": fid, "quantity": "BING_ExpBPow_Bp", "value": bp}
        )
    return matchup_id, pixel_id, f21


def test_geometry_shift_summary_pairs_2_1_with_the_overlaid_2_0():
    with Store.open(":memory:") as store:
        assert compare.geometry_shift_summary(store) is None
        _seed_patched_runaway(store)
        assert compare.geometry_shift_summary(store) is None  # one family only
    with Store.open(":memory:") as store:
        _seed_21(store, ratio=1.25)
        g = compare.geometry_shift_summary(store)
        # paired with the 2.0.1 row (4e-4), not the superseded 2.0 runaway (5e4)
        assert g["new"] == "2.1" and g["old"] == "2.0" and g["old_patches"] == ["2.0.1"]
        assert g["n"] == 1 and g["median_ratio"] == pytest.approx(1.25)
        d = compare.forward_model_domain_summary(store)
        assert d["n"] == 1 and d["n_normalized"] == 1


def test_no_geometry_note_when_2_1_was_fitted_at_the_observed_angles():
    with Store.open(":memory:") as store:
        _seed_21(store, geom="observed")
        assert compare.geometry_shift_summary(store) is None
        assert rst._geometry_change(store) == ""
        assert compare.forward_model_domain_summary(store)["n_normalized"] == 0


def test_pages_state_the_2_1_change_once_with_the_computed_shift():
    with Store.open(":memory:") as store:
        _seed_21(store, ratio=1.25)
        summary = rst.summary_page(store)
        assert "What changed in 2.1" in summary
        assert "**1.25**" in summary and compare.GEOMETRY_RERUN_URL in summary
        assert "2.0 (2.0.1 where re-fitted)" in summary
        methods = rst.methods_page(store=store)
        assert "Retrieval configuration (2.1)" in methods
        assert "**What changed in 2.1.**" in methods
        assert "lies **inside** that trained geometry" in methods
        assert "applied outside its trained geometry for every fit" not in methods
        assert "``2.1`` is a new **re-analysis**" in methods
        # no failed 2.1 retrieval, so no claim that the gallery shows one
        assert "the figure gallery shows one such fit" not in methods


def test_a_2_0_store_keeps_the_2_0_wording():
    with Store.open(":memory:") as store:
        _seed_patched_runaway(store)
        methods = rst.methods_page(store=store)
        assert "Retrieval configuration (2.0)" in methods
        assert "What changed in 2.1" not in methods
        assert "re-analysis**, not a patch" not in methods
        assert "What changed in 2.1" not in rst.summary_page(store)
