"""The 1.0-vs-2.0 section of the report (Prompt 8 Task 2).

The section compares two *databases*, so its failure modes are different from
the rest of the report: it must vanish cleanly when the v1 database is not
given, it must not let a bad v1 take the whole site build down with it, and
the description of what changed must come from one place rather than being
restated on three pages that can then drift apart.
"""

from __future__ import annotations

import pytest

from pab.db.store import Store
from pab.report import rst


def _seed_one(store, matchup_id, *, wmo, cycle, bbp, chl, version, aph=None):
    """A matchup with one BING fit, pixel_id set (the version join needs it)."""
    from pab.argo.summary import persist_summary

    pid = persist_summary(
        store,
        wmo=wmo,
        cycle=cycle,
        summary={
            "mld": 30.0,
            "mld_method": "x",
            "bbp700": 1e-3,
            "chla": 0.1,
            "n_points": 6,
        },
        latitude=20.0,
        longitude=-50.0,
        time="2025-05-01T12:00:00",
    )
    gid = f"G_{cycle}"
    store.upsert("granules", {"granule_id": gid, "data_url": f"s3://b/{gid}.nc"})
    store.upsert(
        "matchups",
        {
            "matchup_id": matchup_id,
            "profile_id": pid,
            "granule_id": gid,
            "n_spectra": 1,
        },
    )
    store.upsert(
        "matchup_pixels",
        {"matchup_id": matchup_id, "ix": 2, "iy": 2, "rank": 1, "flagged": 0},
    )
    pixel_id = store.query(
        "SELECT pixel_id FROM matchup_pixels WHERE matchup_id = ?", (matchup_id,)
    )[0]["pixel_id"]
    fit_id = f"{matchup_id}_v{version}"
    store.upsert(
        "fits",
        {
            "fit_id": fit_id,
            "matchup_id": matchup_id,
            "pixel_id": pixel_id,
            "algorithm": "BING",
            "model_pair": "ExpBPow",
            "chisq": 1.1,
            "success": 1,
            "pab_version": version,
        },
    )
    vals = {"bbp700": bbp, "chl": chl}
    if aph is not None:
        vals["Aph"] = aph
    if version == "2.0":
        vals["Bp"] = 0.02
    for q, v in vals.items():
        store.upsert(
            "fit_results",
            {"fit_id": fit_id, "quantity": f"BING_ExpBPow_{q}", "value": v},
        )
    return fit_id


def _v1_db(tmp_path, *, bbps=(2e-3, 4e-3), name="v1.db"):
    """A frozen-v1-shaped database with 1.0 BING fits on M1/M2."""
    path = tmp_path / name
    with Store.open(str(path)) as s:
        for i, bbp in enumerate(bbps, 1):
            _seed_one(
                s, f"M{i}", wmo=7902220 + i, cycle=i, bbp=bbp, chl=0.10, version="1.0"
            )
    return path


def _v2_store(store, *, bbps=(1e-3, 2e-3)):
    """The matching 2.0 fits: half the b_bp, 20 % more Chl."""
    for i, bbp in enumerate(bbps, 1):
        _seed_one(
            store, f"M{i}", wmo=7902220 + i, cycle=i, bbp=bbp, chl=0.12, version="2.0"
        )


# -- the section appears, with the numbers -----------------------------------
def test_version_section_reports_the_ratio(tmp_path):
    v1 = _v1_db(tmp_path)
    with Store.open(":memory:") as store:
        _v2_store(store)
        out = rst.version_section(store, v1, sortable=False)
        assert "1.0 vs 2.0" in out
        # both seeded pairs are exactly 2.0/1.0 = 0.5
        assert "n = 2" in out
        assert "0.5" in out
        # Chl went the other way (0.12 / 0.10 = 1.2) — the two must not be
        # reported with the same sign of change.
        assert "1.2" in out


def test_version_section_states_what_changed_from_the_constant(tmp_path):
    """The 'what changed' text is one constant, not three copies."""
    v1 = _v1_db(tmp_path)
    with Store.open(":memory:") as store:
        _v2_store(store)
        out = rst.version_section(store, v1, sortable=False)
        assert rst.V2_CHANGES in out, "the section restates the changes itself"
    # And the same constant reaches the Methods page.
    assert rst.V2_CHANGES in rst.methods_page(compare_db=v1)


def test_v2_changes_states_cdom_off_and_window_unchanged():
    """Two claims in the brief that the actual run contradicts.

    `include_cdom_fl = 0` in every 2.0 fit, and `wave_min`/`wave_max` are
    400/700 in *both* releases. Describing either as a 2.0 improvement would
    be a false claim in a published report.
    """
    assert "**off** in this run" in rst.V2_CHANGES
    assert "fit window is unchanged" in rst.V2_CHANGES


# -- the section's absence ----------------------------------------------------
def test_version_section_empty_without_compare_db(caplog):
    """No v1 asked for is not a failure, so it must not log one.

    Without the up-front guard this still returns "" — the broad `except`
    around `gather_version_pair` swallows it — so asserting only on the empty
    string passes for the wrong reason. The absence of a warning is what
    distinguishes "nothing was asked for" from "something went wrong".
    """
    with Store.open(":memory:") as store:
        _v2_store(store)
        with caplog.at_level("WARNING", logger="pab.report"):
            assert rst.version_section(store, None) == ""
        assert caplog.records == []


def test_version_section_empty_when_the_file_is_missing(caplog, tmp_path):
    with Store.open(":memory:") as store:
        _v2_store(store)
        with caplog.at_level("WARNING", logger="pab.report"):
            assert rst.version_section(store, tmp_path / "nope.db") == ""
        assert caplog.records == []


def test_version_section_empty_when_no_matchup_is_shared(tmp_path):
    """A v1 from a different run must produce no section, not bogus pairs."""
    path = tmp_path / "other.db"
    with Store.open(str(path)) as s:
        _seed_one(s, "OTHER", wmo=1, cycle=9, bbp=2e-3, chl=0.1, version="1.0")
    with Store.open(":memory:") as store:
        _v2_store(store)
        assert rst.version_section(store, path) == ""


def test_a_corrupt_v1_does_not_break_the_build(caplog, tmp_path):
    """The build survives an unusable v1 — but says so, loudly.

    A section that silently disappears from a published report is worse than
    one that errors: the site looks complete and the comparison is just gone.
    """
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"this is not a sqlite database")
    with Store.open(":memory:") as store:
        _v2_store(store)
        with caplog.at_level("WARNING", logger="pab.report"):
            assert rst.version_section(store, bad) == ""
        assert any("could not read" in r.message for r in caplog.records)
        written = rst.build_site(
            store, tmp_path / "site", sortable=False, compare_db=bad
        )
        assert written["comparisons"].is_file()


def test_a_v1_sharing_no_matchup_is_logged(caplog, tmp_path):
    """Pointing at the wrong v1 yields an empty section; that must be visible."""
    path = tmp_path / "other.db"
    with Store.open(str(path)) as s:
        _seed_one(s, "OTHER", wmo=1, cycle=9, bbp=2e-3, chl=0.1, version="1.0")
    with Store.open(":memory:") as store:
        _v2_store(store)
        with caplog.at_level("WARNING", logger="pab.report"):
            assert rst.version_section(store, path) == ""
        assert any("shares no fitted matchup" in r.message for r in caplog.records)


# -- the retrieval-failure note ----------------------------------------------
def test_failure_note_counts_non_physical_bbp(tmp_path):
    """0.33 % of real 2.0 fits return b_bp > 1 m^-1; the report must say so."""
    v1 = _v1_db(tmp_path, bbps=(2e-3, 4e-3))
    with Store.open(":memory:") as store:
        _v2_store(store, bbps=(1e-3, 5.0e4))  # the second fit is non-physical
        out = rst.version_section(store, v1, sortable=False)
        assert "Retrieval failures" in out
        assert "1 of 2" in out
        # and that 1.0 produced none of them, which is what makes it 2.0's
        assert "1.0 produce 0 such values" in out
        assert "left in" in out  # not silently filtered


def test_no_failure_note_when_every_fit_is_physical(tmp_path):
    v1 = _v1_db(tmp_path)
    with Store.open(":memory:") as store:
        _v2_store(store)
        assert "Retrieval failures" not in rst.version_section(store, v1, sortable=False)


def test_aph_is_not_given_its_own_statistics(tmp_path):
    """`chl = Aph / 0.05582`, so an Aph line would duplicate the Chl line."""
    v1 = tmp_path / "v1.db"
    with Store.open(str(v1)) as s:
        _seed_one(s, "M1", wmo=1, cycle=1, bbp=2e-3, chl=0.10, aph=0.0056, version="1.0")
    with Store.open(":memory:") as store:
        _seed_one(
            store, "M1", wmo=1, cycle=1, bbp=1e-3, chl=0.12, aph=0.0067, version="2.0"
        )
        out = rst.version_section(store, v1, sortable=False)
        assert "**A_ph** —" not in out
        assert "fixed rescaling" in out  # said once, instead


# -- the figures --------------------------------------------------------------
def test_static_figures_and_bp_histogram_at_scale(tmp_path):
    v1 = _v1_db(tmp_path)
    out_dir = tmp_path / "site"
    with Store.open(":memory:") as store:
        _v2_store(store)
        out = rst.version_section(store, v1, outdir=out_dir, max_interactive=1)
        dest = out_dir / "_static" / "comparisons"
        assert (dest / "v2_vs_v1_bbp700.png").is_file()
        assert (dest / "v2_vs_v1_chl.png").is_file()
        assert (dest / "v2_bp_hist.png").is_file()
        assert ".. raw:: html" not in out  # no Bokeh embed at scale
        assert "B_p" in out and "prior" in out


def test_bp_histogram_absent_when_bp_was_not_fitted(tmp_path):
    """1.0-only stores have no Bp column; the block must drop out, not raise."""
    v1 = _v1_db(tmp_path)
    out_dir = tmp_path / "site"
    with Store.open(":memory:") as store:
        _v2_store(store)
        store.conn.execute(
            "DELETE FROM fit_results WHERE quantity = 'BING_ExpBPow_Bp'"
        )
        out = rst.version_section(store, v1, outdir=out_dir, max_interactive=1)
        assert not (out_dir / "_static" / "comparisons" / "v2_bp_hist.png").is_file()
        assert "v2_bp_hist.png" not in out


def test_clip_percentile_bounds_the_axes_and_counts_off_scale():
    """An outlier must change the title, not silently vanish from the plot."""
    pd = pytest.importorskip("pandas")
    from pab.plotting import population

    df = pd.DataFrame(
        {"x": [1e-3] * 99 + [1e-3], "y": [1e-3] * 99 + [1e4]},
    )
    fig = population.comparison_scatter(df, "y", "x", clip_percentile=99.0)
    ax = fig.axes[0]
    assert ax.get_ylim()[1] < 1e4, "the outlier still sets the axis range"
    assert "off-scale" in ax.get_title()


# -- wiring -------------------------------------------------------------------
def test_build_site_threads_compare_db_to_every_page(tmp_path):
    v1 = _v1_db(tmp_path)
    with Store.open(":memory:") as store:
        _v2_store(store)
        written = rst.build_site(
            store, tmp_path / "site", sortable=False, compare_db=v1
        )
        assert "1.0 vs 2.0" in written["comparisons"].read_text()
        assert "1.0 vs 2.0 (elastic vs inelastic)" in written["summary"].read_text()
        methods = written["methods"].read_text()
        assert "Two databases" in methods
        assert "pab_version`` semantics" in methods


def test_build_site_unchanged_without_compare_db(tmp_path):
    with Store.open(":memory:") as store:
        _v2_store(store)
        written = rst.build_site(store, tmp_path / "site", sortable=False)
        assert "1.0 vs 2.0" not in written["comparisons"].read_text()
        assert "1.0 vs 2.0" not in written["summary"].read_text()
        methods = written["methods"].read_text()
        assert "Two databases" not in methods
        # the 2.0 configuration still describes this release on its own
        assert rst.V2_CHANGES in methods


def test_cli_compare_db_reaches_build_site(tmp_path, monkeypatch):
    """`--compare-db` is forwarded, not accepted-and-ignored (the Prompt 5 trap)."""
    from pab import pipeline
    from pab.report import rst as _rst

    db = tmp_path / "v2.db"
    with Store.open(str(db)) as store:
        _v2_store(store)
    seen = {}

    def _fake_build_site(store, outdir, **kw):
        seen.update(kw)
        return {}

    monkeypatch.setattr(_rst, "build_site", _fake_build_site)
    rc = pipeline.main(
        [
            "--db",
            str(db),
            "--emit-site",
            str(tmp_path / "site"),
            "--compare-db",
            "/path/to/v1.db",
        ]
    )
    assert rc == 0
    assert seen.get("compare_db") == "/path/to/v1.db"


def test_ratio_is_reported_by_level_not_as_one_number(tmp_path):
    """A single median invites use as a correction factor; the shift is not flat.

    In the real data the tercile ratios run 0.66 / 0.74 / 0.81, and far wider
    at the extremes — so the section must show the trend, not just the median.
    """
    v1 = tmp_path / "v1.db"
    n = 60
    with Store.open(str(v1)) as s:
        for i in range(n):
            _seed_one(
                s, f"M{i}", wmo=7900000 + i, cycle=i, bbp=1e-4 * (i + 1),
                chl=0.1, version="1.0",
            )
    with Store.open(":memory:") as store:
        for i in range(n):
            # ratio ramps 0.2 -> 0.9 with the 1.0 level
            r = 0.2 + 0.7 * i / (n - 1)
            _seed_one(
                store, f"M{i}", wmo=7900000 + i, cycle=i, bbp=1e-4 * (i + 1) * r,
                chl=0.12, version="2.0",
            )
        out = rst.version_section(store, v1, sortable=False)
        assert "clearest third" in out and "most-scattering third" in out
        assert "not** a correction factor" in out


def test_no_level_split_on_a_handful_of_matchups(tmp_path):
    """Terciles of 2 points are noise dressed as a trend."""
    v1 = _v1_db(tmp_path)
    with Store.open(":memory:") as store:
        _v2_store(store)
        assert "clearest third" not in rst.version_section(store, v1, sortable=False)


def test_captions_contain_no_matplotlib_mathtext(tmp_path):
    """`$b_{bp}$` is an axis label; in RST it renders as literal dollar signs."""
    v1 = _v1_db(tmp_path)
    out_dir = tmp_path / "site"
    with Store.open(":memory:") as store:
        _v2_store(store)
        out = rst.version_section(store, v1, outdir=out_dir, max_interactive=1)
    assert "$" not in out, (
        "Matplotlib mathtext leaked into the page:\n"
        + "\n".join(ln for ln in out.splitlines() if "$" in ln)
    )


def test_clear_water_result_is_framed_as_a_result(tmp_path):
    """Q2: JXP confirmed the clear-water behaviour is expected physics."""
    v1 = tmp_path / "v1.db"
    n = 120
    with Store.open(str(v1)) as s:
        for i in range(n):
            _seed_one(
                s, f"M{i}", wmo=7900000 + i, cycle=i, bbp=1e-4 * (i + 1),
                chl=0.1, version="1.0",
            )
    with Store.open(":memory:") as store:
        for i in range(n):
            r = 0.2 + 0.7 * i / (n - 1)
            _seed_one(
                store, f"M{i}", wmo=7900000 + i, cycle=i,
                bbp=1e-4 * (i + 1) * r, chl=0.12, version="2.0",
            )
        out = rst.version_section(store, v1, sortable=False)
        assert "Result:" in out, "the level dependence is still framed as a caveat"
        assert "expected behaviour of the physics" in out
        assert "Raman" in out and "inventing particulate backscatter" in out


def test_bp_block_reports_the_pile_up_at_both_bounds(tmp_path):
    """Q3: the censoring must be stated, not left to the panel title."""
    import numpy as np

    v1 = _v1_db(tmp_path)
    out_dir = tmp_path / "site"
    with Store.open(":memory:") as store:
        _v2_store(store)
        # put Bp hard against both bounds
        for fid, bp in (("M1_v2.0", 0.004), ("M2_v2.0", 0.05)):
            store.upsert(
                "fit_results",
                {"fit_id": fid, "quantity": "BING_ExpBPow_Bp", "value": bp},
            )
        out = rst.version_section(store, v1, outdir=out_dir, max_interactive=1)
        assert "both bounds" in out or "both ends" in out
        assert "censored" in out
        assert np.isfinite(0.0)  # keep numpy import meaningful
