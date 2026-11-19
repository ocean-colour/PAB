"""The Global explorer (claude_prompts/viz_tools.md, Q&A / Global explorer).

In-memory store, no network, no server.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pab.db.store import Store
from pab.tests.test_viz_argo_pace import _seed
from pab.viz import data
from pab.viz import global_explorer as gx


def _frame(n=6):
    rng = np.random.default_rng(0)
    pace = np.full(n, 1e-3)
    argo = pace * np.array([0.5, 1.0, 2.0, 1.0, 3.0, 1.0])[:n]
    return pd.DataFrame({
        "matchup_id": [f"m{i}" for i in range(n)], "fit_id": [f"f{i}" for i in range(n)],
        "wmo": np.arange(n) + 1000, "cycle": np.ones(n, int),
        "latitude": np.linspace(-50, 50, n), "longitude": np.linspace(-150, 150, n),
        "time": [f"2025-0{1 + i % 9}-15T12:00:00" for i in range(n)],
        "pab_version": ["2.1"] * n, "bbp_argo": argo,
        "bbp_bing": np.where(np.arange(n) == 5, 2.0, pace),       # row 5 implausible
        "chla_argo": rng.uniform(0.1, 1, n), "chl_bing": rng.uniform(0.1, 1, n),
        "chisq": [1, 2, 40, 1, 1, 1], "bbp_bing_implausible": np.arange(n) == 5,
        "success": [1, 1, 1, 0, 1, 1], "distance_km": np.ones(n),
        "dtime_hours": [1, 2, 3, 4, 20, 5], "adg": np.full(n, 0.02),
        "sdg": np.full(n, 0.015), "beta": np.full(n, 0.5),
    })


def test_explorer_frame_reads_the_store():
    with Store.open(":memory:") as store:
        *_, f21 = _seed(store)
        df = data.explorer_frame(store, "2.1")
        assert list(df["fit_id"]) == [f21]
        for col in ("success", "distance_km", "dtime_hours", "adg", "sdg", "beta"):
            assert col in df
        assert df["beta"].iloc[0] == pytest.approx(0.8)
        assert gx.derive(df)["bbp_pace"].iloc[0] == pytest.approx(4.8e-4)


def test_derive_and_filters():
    d = gx.derive(_frame())
    assert d["dbbp"].iloc[:3].tolist() == pytest.approx([-0.5, 0.0, 1.0])
    assert d["lr_bbp"].iloc[2] == pytest.approx(np.log10(2))
    x, y = gx.mercator(180.0, 0.0)
    assert x == pytest.approx(20037508.34, rel=1e-6) and y == pytest.approx(0.0, abs=1e-6)
    out = gx.apply_filters(d, gx.Filters())          # defaults: gate + success only
    assert "1003" not in out["wmo"].astype(str).tolist()       # LM failure dropped
    gated = out[out["wmo"] == 1005].iloc[0]
    assert np.isnan(gated["bbp_pace"]) and np.isnan(gated["dbbp"])  # row stays, b_bp gone
    assert np.isfinite(gated["chl_pace"])
    out = gx.apply_filters(d, gx.Filters(chisq_max=10, dt_max=10, success_only=False))
    assert sorted(out["wmo"]) == [1000, 1001, 1003, 1005]


def test_ranges_and_histogram():
    var = gx.VARIABLES["dbbp"]
    assert gx.default_range([5.0, 140.0], var) == (-1.0, 1.0)
    lo, hi = gx.default_range(np.logspace(-4, -2, 101), gx.VARIABLES["bbp_argo"])
    assert 1e-4 < lo < hi < 1e-2
    edges, counts, n_lo, n_hi = gx.histogram([-2.0, -0.5, 0.0, 0.5, 141.0], var, -1, 1, bins=4)
    assert (n_lo, n_hi) == (1, 1) and counts.sum() == 3 and len(edges) == 5
    assert gx.parse_number("1e-3") == 1e-3 and gx.parse_number("x") is None


def test_stats_are_argo_over_pace():
    d = gx.apply_filters(gx.derive(_frame()), gx.Filters())
    s = gx.stats_rows(d)
    assert s["bbp"]["n"] == 4                       # 6 − LM failure − gated
    assert s["bbp"]["median_ratio"] == pytest.approx(1.5)
    assert s["bbp"]["median_dbbp"] == pytest.approx(0.5)
    assert s["chl"]["n"] == 5


def test_global_tab_builds_and_opens_a_matchup():
    opened = []
    with Store.open(":memory:") as store:
        _seed(store)
        tab = gx.GlobalTab(store, ":memory:", open_matchup=lambda *a: opened.append(a))
        assert len(tab.src.data["x"]) == 1
        tab.variable.value = "bbp_pace"                # log colour, auto range
        assert tab.color_bar.color_mapper is tab.log_mapper
        tab.low.value, tab.high.value = "1e-4", "1e-2"
        assert tab.state.ranges["bbp_pace"] == (1e-4, 1e-2)
        tab.low.value = "-1"                           # invalid on a log scale
        assert "low &gt; 0" in tab.status.text
        tab.src.selected.indices = [0]
        assert "WMO 7902226" in tab.card.text and not tab.open_btn.disabled
        tab._on_open()
        assert opened == [(7902226, 5, "2.1")]
        assert "1 selected" in tab.stats.text
    gx._frames.clear()
